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
input bool   InpShowConfluence    = true;                     // Also fetch/show the confluence score

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
//| Draws (or redraws) a zone rectangle. Recreate-rather-than-update, |
//| same pattern frontend/src/components/PriceChart.tsx uses for its |
//| price lines - simplest correct way to reflect zones that can     |
//| disappear or shift between polls.                                  |
//+------------------------------------------------------------------+
void DrawZone(string name, datetime t1, double p1, datetime t2, double p2, color clr)
  {
   ObjectDelete(0, name);
   ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FILL, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
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
void DrawCornerLabel(string name, int y, string text, color clr)
  {
   ObjectDelete(0, name);
   ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
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
//| One full refresh: fetch /smc (+ /confluence), clear everything   |
//| this EA previously drew, redraw from the fresh response.         |
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

   string bias    = smc["bias"].ToStr();
   color  biasClr = BiasColor(bias);

   DrawCornerLabel(OBJ_PREFIX + "status", 10, "Trading Ambassador -- " + symbol + " " + tf, COLOR_NEUTRAL);
   DrawCornerLabel(OBJ_PREFIX + "bias", 28, "Bias: " + bias, biasClr);

   datetime rightEdge = iTime(_Symbol, _Period, 0) + InpZoneExtensionBars * PeriodSeconds();

   //--- order blocks (unmitigated only - matches the dashboard's own
   // decluttering call: a mitigated zone is history, not worth watching)
   int obCount = smc["order_blocks"].Size();
   for(int i = 0; i < obCount; i++)
     {
      if(smc["order_blocks"][i]["mitigated"].ToBool())
         continue;
      string   dir     = smc["order_blocks"][i]["direction"].ToStr();
      datetime created  = ParseIsoUtcToServerTime(smc["order_blocks"][i]["created_at"].ToStr());
      double   lo       = smc["order_blocks"][i]["zone_low"].ToDbl();
      double   hi       = smc["order_blocks"][i]["zone_high"].ToDbl();
      DrawZone(OBJ_PREFIX + "ob_" + IntegerToString(i), created, lo, rightEdge, hi, BiasColor(dir));
     }

   //--- fair value gaps (not fully mitigated)
   int fvgCount = smc["fair_value_gaps"].Size();
   for(int i = 0; i < fvgCount; i++)
     {
      if(smc["fair_value_gaps"][i]["mitigated_pct"].ToDbl() >= 100.0)
         continue;
      string   dir     = smc["fair_value_gaps"][i]["direction"].ToStr();
      datetime created  = ParseIsoUtcToServerTime(smc["fair_value_gaps"][i]["created_at"].ToStr());
      double   lo       = smc["fair_value_gaps"][i]["lower"].ToDbl();
      double   hi       = smc["fair_value_gaps"][i]["upper"].ToDbl();
      DrawZone(OBJ_PREFIX + "fvg_" + IntegerToString(i), created, lo, rightEdge, hi, BiasColor(dir));
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

   //--- premium/discount status (a compact label, not a zone - keeps
   // this EA's drawing surface to what the plan actually scoped)
   if(smc["premium_discount"].type != jtNULL && smc["premium_discount"].type != jtUNDEF)
     {
      string pdStatus = smc["premium_discount"]["status"].ToStr();
      DrawCornerLabel(OBJ_PREFIX + "pd", 64, "Price: " + pdStatus, COLOR_NEUTRAL);
     }

   if(InpShowConfluence)
      RefreshConfluence(symbol, tf);
  }

//+------------------------------------------------------------------+
//| Separate call to /confluence - kept optional (InpShowConfluence)  |
//| since it's a second WebRequest per poll.                          |
//+------------------------------------------------------------------+
void RefreshConfluence(string symbol, string tf)
  {
   string url = InpApiBaseUrl + "/api/markets/" + UrlEncodeSymbol(symbol) + "/confluence?timeframe=" + tf;
   string body;
   if(!HttpGet(url, body))
      return; // the status label already shows API health; don't double-warn

   CJAVal c;
   if(!c.Deserialize(body))
      return;

   int    score    = (int)c["score"].ToInt();
   int    maxScore = (int)c["max_score"].ToInt();
   double pct      = c["score_pct"].ToDbl();
   string bias     = c["bias"].ToStr();

   DrawCornerLabel(OBJ_PREFIX + "confluence", 46,
                   StringFormat("Confluence: %d/%d (%.0f%%)", score, maxScore, pct),
                   BiasColor(bias));
  }
//+------------------------------------------------------------------+
