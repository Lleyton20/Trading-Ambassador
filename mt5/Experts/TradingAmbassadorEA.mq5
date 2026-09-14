//+------------------------------------------------------------------+
//|                                        TradingAmbassadorEA.mq5   |
//|                                                                  |
//| Draws Trading Ambassador's live SMC analysis (order blocks,      |
//| FVGs, BOS/CHoCH, bias, confluence score) directly on the MT5     |
//| chart, by polling the project's own FastAPI backend.             |
//|                                                                  |
//| DISPLAY ONLY. This EA never calls OrderSend or any trade         |
//| function - Trading Ambassador's core rule, carried over from the |
//| Python backend, is "presents evidence, never trades" (see        |
//| backend/README.md, "Key design decisions"). Do not add trading   |
//| logic to this file.                                              |
//|                                                                  |
//| SETUP (see the project README's "MT5 Expert Advisor" section     |
//| for the full walkthrough):                                       |
//|   1. Backend running and reachable (MARKET_DATA_PROVIDER=deriv   |
//|      in backend/.env for live data).                             |
//|   2. Tools -> Options -> Expert Advisors -> allow WebRequest ->   |
//|      add InpApiBaseUrl to the list (MT5 will silently refuse     |
//|      the request otherwise).                                     |
//|   3. Copy ../Include/JAson.mqh to <data folder>/MQL5/Include/.    |
//|   4. Attach to a chart, enable Auto Trading (MT5 gates ALL EA     |
//|      execution behind this, even display-only ones).             |
//|   5. Set InpBackendSymbol if the chart's own symbol name isn't    |
//|      exactly one of our backend's instrument keys (EURUSD,        |
//|      GBPUSD, USDJPY, XAUUSD, CRASH500, CRASH1000, BOOM500,        |
//|      BOOM1000, V75) - Deriv MT5's exact synthetic-index symbol    |
//|      strings vary and can't be hardcoded here without a live      |
//|      account to check against.                                    |
//+------------------------------------------------------------------+
#property copyright "Trading Ambassador"
#property link      "https://github.com/Lleyton20/Trading-Ambassador"
#property version   "1.00"
#property strict
#property description "Live Trading Ambassador SMC overlay (order blocks, FVGs, BOS/CHoCH, bias, confluence). Display only - never trades."

#include <JAson.mqh>

//--- inputs ----------------------------------------------------------
input string InpApiBaseUrl        = "http://127.0.0.1:8000"; // Backend base URL
input string InpBackendSymbol     = "";                       // Backend instrument key (blank = use chart symbol)
input string InpTimeframeOverride = "";                       // Backend timeframe (blank = derive from chart period)
input int    InpPollSeconds       = 30;                       // Seconds between refreshes (min 5)
input int    InpHttpTimeoutMs     = 5000;                     // WebRequest timeout, ms
input int    InpZoneExtensionBars = 30;                       // Bars an active zone extends past "now"
input int    InpZoneMaxAgeBars    = 60;                       // Zones don't visually extend further back than this
input int    InpMaxZonesPerType   = 4;                        // Most recent unmitigated order blocks/FVGs to draw
input bool   InpShowConfluence    = true;                     // Also fetch/show the confluence score
input bool   InpShowHtfZones      = true;                     // Also draw the higher-timeframe's zones (dashed)

//--- bias colors: kept identical to frontend/src/colors.ts, so the EA's
// chart markup and the web dashboard agree visually.
#define COLOR_BEARISH  C'239,68,68'   // #ef4444
#define COLOR_BULLISH  C'125,211,252' // #7dd3fc
#define COLOR_NEUTRAL  C'148,163,184' // #94a3b8

#define OBJ_PREFIX "TA_"

bool g_apiWarned = false;

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
  {
   EventSetTimer(MathMax(InpPollSeconds, 5));
   RefreshFromBackend(); // don't wait for the first timer tick
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, OBJ_PREFIX);
  }

//+------------------------------------------------------------------+
//| Timer: this is the EA's only real loop                           |
//+------------------------------------------------------------------+
void OnTimer()
  {
   RefreshFromBackend();
  }

//+------------------------------------------------------------------+
//| Intentionally empty - display-only EA, see file header. Do not   |
//| add OrderSend/CTrade calls here or anywhere else in this file.   |
//+------------------------------------------------------------------+
void OnTick()
  {
  }

//+------------------------------------------------------------------+
//| Which backend instrument key to query                            |
//+------------------------------------------------------------------+
string BackendSymbol()
  {
   return (InpBackendSymbol != "") ? InpBackendSymbol : _Symbol;
  }

//+------------------------------------------------------------------+
//| Which backend timeframe string to query - MT5's PERIOD_* names   |
//| happen to match the backend's M1/M5/.../W1 strings directly.     |
//+------------------------------------------------------------------+
string BackendTimeframe()
  {
   if(InpTimeframeOverride != "")
      return InpTimeframeOverride;

   switch(_Period)
     {
      case PERIOD_M1:  return "M1";
      case PERIOD_M5:  return "M5";
      case PERIOD_M15: return "M15";
      case PERIOD_M30: return "M30";
      case PERIOD_H1:  return "H1";
      case PERIOD_H4:  return "H4";
      case PERIOD_D1:  return "D1";
      case PERIOD_W1:  return "W1";
      default:         return "H1"; // unsupported chart period - fall back rather than send a bad request
     }
  }

//+------------------------------------------------------------------+
//| Minimal, deliberately narrow: just enough to survive a space in  |
//| a symbol name (Deriv's synthetic indices are commonly displayed  |
//| with spaces, e.g. "Volatility 75"). Not a general URL encoder.   |
//+------------------------------------------------------------------+
string UrlEncodeSymbol(string s)
  {
   string out = s;
   StringReplace(out, " ", "%20");
   return out;
  }

//+------------------------------------------------------------------+
//| The API returns UTC timestamps like "2026-09-11T04:00:00Z"       |
//| (verified against a live response, not guessed). MT5's chart     |
//| time axis uses broker SERVER time, not GMT, so a zone drawn at   |
//| the raw UTC value would land on the wrong candles whenever the   |
//| broker isn't on UTC - this converts to the server-time           |
//| equivalent before anything gets drawn.                            |
//+------------------------------------------------------------------+
datetime ParseIsoUtcToServerTime(string iso)
  {
   string s = iso;
   StringReplace(s, "T", " ");
   StringReplace(s, "Z", "");
   datetime utc = StringToTime(s); // StringToTime accepts "yyyy-mm-dd hh:mi:ss" directly
   return utc + (TimeTradeServer() - TimeGMT());
  }

//+------------------------------------------------------------------+
//| GET url, return the response body via out_body. False on any     |
//| failure (unreachable, not whitelisted, non-200) - callers show   |
//| that as an on-chart status rather than leaving stale/no data.    |
//+------------------------------------------------------------------+
bool HttpGet(string url, string &out_body)
  {
   char   post[];
   char   result[];
   string result_headers;

   ResetLastError();
   int status = WebRequest("GET", url, "", InpHttpTimeoutMs, post, result, result_headers);

   if(status == -1)
     {
      if(!g_apiWarned)
        {
         Print("Trading Ambassador EA: WebRequest failed (error ", GetLastError(),
               "). In MT5: Tools -> Options -> Expert Advisors -> 'Allow WebRequest for ",
               "listed URL' -> add '", InpApiBaseUrl, "', then remove and re-attach this EA.");
         g_apiWarned = true;
        }
      return false;
     }
   if(status != 200)
     {
      Print("Trading Ambassador EA: backend returned HTTP ", status, " for ", url);
      return false;
     }

   g_apiWarned = false;
   out_body = CharArrayToString(result, 0, -1, CP_UTF8);
   return true;
  }

//+------------------------------------------------------------------+
color BiasColor(string bias)
  {
   if(bias == "bearish")
      return COLOR_BEARISH;
   if(bias == "bullish")
      return COLOR_BULLISH;
   return COLOR_NEUTRAL;
  }

//+------------------------------------------------------------------+
//| Draws (or redraws) a zone as an OUTLINED box (not filled) - a     |
//| filled rectangle per zone, uncapped, is what made this unreadable |
//| in practice: overlapping solid blocks bury the candles. An        |
//| outline reads as "these two lines bound a zone" instead of a      |
//| wall of color, while staying on the same OBJ_RECTANGLE object     |
//| type already verified against MQL5's docs (a different object    |
//| type - trend line pairs - would add unverified surface for no     |
//| real benefit). Recreate-rather-than-update, same pattern          |
//| frontend/src/components/PriceChart.tsx uses for its price lines.  |
//+------------------------------------------------------------------+
void DrawZone(string name, datetime t1, double p1, datetime t2, double p2, color clr, ENUM_LINE_STYLE style=STYLE_SOLID)
  {
   ObjectDelete(0, name);
   ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FILL, false);
   ObjectSetInteger(0, name, OBJPROP_BACK, false);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

//+------------------------------------------------------------------+
void DrawLabelAtPrice(string name, datetime t, double p, string text, color clr, ENUM_ANCHOR_POINT anchor)
  {
   ObjectDelete(0, name);
   ObjectCreate(0, name, OBJ_TEXT, 0, t, p);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, anchor);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

//+------------------------------------------------------------------+
//| Top-right status/bias/confluence panel. CORNER_RIGHT_UPPER alone  |
//| isn't enough - a label's text still grows rightward off-screen    |
//| from its anchor point by default, so ANCHOR_RIGHT_UPPER is set    |
//| too, which makes the text grow leftward from the right edge and   |
//| keeps it fully on-chart.                                          |
//+------------------------------------------------------------------+
void DrawCornerLabel(string name, int y, string text, color clr)
  {
   ObjectDelete(0, name);
   ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_RIGHT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_RIGHT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 10);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 10);
   ObjectSetString(0, name, OBJPROP_FONT, "Arial Bold");
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

//+------------------------------------------------------------------+
//| Draws order blocks + FVGs from one /smc response. `namePrefix`   |
//| keeps LTF and HTF zones as separate named objects (both cleaned  |
//| up together by the ObjectsDeleteAll(0, OBJ_PREFIX) at the start  |
//| of every refresh); `style` is how LTF vs HTF zones are told      |
//| apart on-chart (solid vs dashed) without adding more text.       |
//+------------------------------------------------------------------+
void DrawZonesFromSmc(CJAVal &smcData, string namePrefix, datetime oldestZoneEdge, datetime rightEdge, ENUM_LINE_STYLE style)
  {
   int obCount = smcData["order_blocks"].Size();
   int obDrawn = 0;
   for(int i = obCount - 1; i >= 0 && obDrawn < InpMaxZonesPerType; i--)
     {
      if(smcData["order_blocks"][i]["mitigated"].ToBool())
         continue;
      string   dir      = smcData["order_blocks"][i]["direction"].ToStr();
      datetime created   = ParseIsoUtcToServerTime(smcData["order_blocks"][i]["created_at"].ToStr());
      datetime leftEdge  = (created > oldestZoneEdge) ? created : oldestZoneEdge;
      double   lo        = smcData["order_blocks"][i]["zone_low"].ToDbl();
      double   hi        = smcData["order_blocks"][i]["zone_high"].ToDbl();
      DrawZone(OBJ_PREFIX + namePrefix + "ob_" + IntegerToString(i), leftEdge, lo, rightEdge, hi, BiasColor(dir), style);
      obDrawn++;
     }

   int fvgCount = smcData["fair_value_gaps"].Size();
   int fvgDrawn = 0;
   for(int i = fvgCount - 1; i >= 0 && fvgDrawn < InpMaxZonesPerType; i--)
     {
      if(smcData["fair_value_gaps"][i]["mitigated_pct"].ToDbl() >= 100.0)
         continue;
      string   dir      = smcData["fair_value_gaps"][i]["direction"].ToStr();
      datetime created   = ParseIsoUtcToServerTime(smcData["fair_value_gaps"][i]["created_at"].ToStr());
      datetime leftEdge  = (created > oldestZoneEdge) ? created : oldestZoneEdge;
      double   lo        = smcData["fair_value_gaps"][i]["lower"].ToDbl();
      double   hi        = smcData["fair_value_gaps"][i]["upper"].ToDbl();
      DrawZone(OBJ_PREFIX + namePrefix + "fvg_" + IntegerToString(i), leftEdge, lo, rightEdge, hi, BiasColor(dir), style);
      fvgDrawn++;
     }
  }

//+------------------------------------------------------------------+
//| One full refresh: fetch /smc + /confluence for the chart's own   |
//| timeframe, then (if enabled) /smc again for whichever higher     |
//| timeframe /confluence itself says is the HTF - same HTF_MAP the  |
//| backend's confluence engine already uses (app/confluence/engine.py),|
//| not a second mapping reimplemented here. Clears everything this  |
//| EA previously drew, then redraws from the fresh responses.       |
//+------------------------------------------------------------------+
void RefreshFromBackend()
  {
   string symbol = BackendSymbol();
   string tf     = BackendTimeframe();

   ObjectsDeleteAll(0, OBJ_PREFIX);

   string smcUrl = InpApiBaseUrl + "/api/markets/" + UrlEncodeSymbol(symbol) + "/smc?timeframe=" + tf;
   string smcBody;
   if(!HttpGet(smcUrl, smcBody))
     {
      DrawCornerLabel(OBJ_PREFIX + "status", 10, "Trading Ambassador: API unreachable", COLOR_BEARISH);
      return;
     }

   CJAVal smc;
   if(!smc.Deserialize(smcBody))
     {
      Print("Trading Ambassador EA: failed to parse /smc response");
      DrawCornerLabel(OBJ_PREFIX + "status", 10, "Trading Ambassador: bad response", COLOR_BEARISH);
      return;
     }

   string bias = smc["bias"].ToStr();

   //--- confluence - fetched here (not a separate later call) because
   // its htf_timeframe is what tells us which higher timeframe to also
   // pull zones for below.
   bool   haveConfluence = false;
   int    confScore = 0, confMax = 0;
   double confPct = 0.0;
   string confBias = "", htfTimeframe = "";
   if(InpShowConfluence || InpShowHtfZones)
     {
      string confUrl = InpApiBaseUrl + "/api/markets/" + UrlEncodeSymbol(symbol) + "/confluence?timeframe=" + tf;
      string confBody;
      if(HttpGet(confUrl, confBody))
        {
         CJAVal c;
         if(c.Deserialize(confBody))
           {
            haveConfluence = true;
            confScore    = (int)c["score"].ToInt();
            confMax      = (int)c["max_score"].ToInt();
            confPct      = c["score_pct"].ToDbl();
            confBias     = c["bias"].ToStr();
            htfTimeframe = c["htf_timeframe"].ToStr();
           }
        }
     }

   //--- top-right panel: status, bias, confluence, price status - all in
   // one place, clean and out of the way of the price action.
   DrawCornerLabel(OBJ_PREFIX + "status", 10, "Trading Ambassador -- " + symbol + " " + tf, COLOR_NEUTRAL);
   DrawCornerLabel(OBJ_PREFIX + "bias", 28, "Bias: " + bias, BiasColor(bias));
   if(InpShowConfluence && haveConfluence)
      DrawCornerLabel(OBJ_PREFIX + "confluence", 46,
                      StringFormat("Confluence: %d/%d (%.0f%%)", confScore, confMax, confPct),
                      BiasColor(confBias));

   int nextY = 64;
   if(smc["premium_discount"].type != jtNULL && smc["premium_discount"].type != jtUNDEF)
     {
      string pdStatus = smc["premium_discount"]["status"].ToStr();
      DrawCornerLabel(OBJ_PREFIX + "pd", nextY, "Price: " + pdStatus, COLOR_NEUTRAL);
      nextY += 18;
     }
   if(InpShowHtfZones && haveConfluence && htfTimeframe != "")
      DrawCornerLabel(OBJ_PREFIX + "htf", nextY, "HTF (" + htfTimeframe + ", dashed): " + confBias, BiasColor(confBias));

   datetime rightEdge = iTime(_Symbol, _Period, 0) + InpZoneExtensionBars * PeriodSeconds();
   // A zone's box never visually extends further back than this, even if
   // it genuinely formed long ago and is still technically unmitigated -
   // on higher timeframes (D1+) an honestly-old zone would otherwise
   // stretch across most of the visible chart.
   datetime oldestZoneEdge = iTime(_Symbol, _Period, (int)MathMin(InpZoneMaxAgeBars, iBars(_Symbol, _Period) - 1));

   //--- this chart's own timeframe: solid outlines
   DrawZonesFromSmc(smc, "", oldestZoneEdge, rightEdge, STYLE_SOLID);

   //--- higher timeframe's zones, visible on this (lower) timeframe chart:
   // dashed outlines, same price levels, one extra WebRequest per poll.
   if(InpShowHtfZones && haveConfluence && htfTimeframe != "" && htfTimeframe != tf)
     {
      string htfUrl = InpApiBaseUrl + "/api/markets/" + UrlEncodeSymbol(symbol) + "/smc?timeframe=" + htfTimeframe;
      string htfBody;
      if(HttpGet(htfUrl, htfBody))
        {
         CJAVal htfSmc;
         if(htfSmc.Deserialize(htfBody))
            DrawZonesFromSmc(htfSmc, "htf_", oldestZoneEdge, rightEdge, STYLE_DASH);
        }
     }

   //--- BOS/CHoCH markers - most recent few only, same decluttering
   // reasoning as the dashboard's chart component
   int evCount = smc["structure_events"].Size();
   int evStart = MathMax(0, evCount - 6);
   for(int i = evStart; i < evCount; i++)
     {
      string   dir   = smc["structure_events"][i]["direction"].ToStr();
      datetime t     = ParseIsoUtcToServerTime(smc["structure_events"][i]["timestamp"].ToStr());
      double   price = smc["structure_events"][i]["price"].ToDbl();
      string   label = smc["structure_events"][i]["event_type"].ToStr();
      ENUM_ANCHOR_POINT anchor = (dir == "bullish") ? ANCHOR_UPPER : ANCHOR_LOWER;
      DrawLabelAtPrice(OBJ_PREFIX + "ev_" + IntegerToString(i), t, price, label, BiasColor(dir), anchor);
     }
  }
//+------------------------------------------------------------------+
