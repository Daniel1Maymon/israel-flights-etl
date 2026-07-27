import React, { createContext, useContext, useState, useEffect } from 'react';

type Language = 'en' | 'he';

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string) => string;
  isRTL: boolean;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

// Translation data
const translations = {
  en: {
    // Navigation
    'nav.dashboard': 'Dashboard',
    'nav.airlines': 'Airlines',
    'nav.settings': 'Settings',
    'nav.rankings': 'Rankings',
    'nav.airlinePerformance': 'Airline Performance',
    'nav.insights': 'Insights',
    'nav.recovery': "Who's Back",
    'nav.flightBoard': 'Flight Board',
    'nav.primary': 'Primary navigation',

    // Theme
    'theme.toggle': 'Toggle theme',
    'theme.light': 'Light',
    'theme.dark': 'Dark',
    
    // Language
    'language.toggle': 'Toggle language',
    'language.english': 'English',
    'language.hebrew': 'עברית',
    
    // Dashboard
    'dashboard.title': 'RankAir – Compare Airline Performance at TLV',
    'dashboard.subtitle.line1': 'See which airlines operate on time before you book, including cancellation history',
    'dashboard.subtitle.line2': 'Based on official Israel Airports Authority flight data, updated every 15 minutes and tracked over time',
    'dashboard.filters': 'Filters',
    'dashboard.search': 'Search airlines...',
    
    // Filters
    'filters.destination': 'Destination',
    'filters.selectDestination': 'Select destination',
    'filters.allDestinations': 'All Destinations',
    'filters.dateRange': 'Date Range',
    'filters.allTime': 'All Time',
    'filters.last7Days': 'Last 7 Days',
    'filters.last30Days': 'Last 30 Days',
    'filters.last90Days': 'Last 90 Days',
    'filters.lastYear': 'Last Year',
    'filters.dayOfWeek': 'Day of Week',
    'filters.allDays': 'All Days',
    'filters.monday': 'Monday',
    'filters.tuesday': 'Tuesday',
    'filters.wednesday': 'Wednesday',
    'filters.thursday': 'Thursday',
    'filters.friday': 'Friday',
    'filters.saturday': 'Saturday',
    'filters.sunday': 'Sunday',
    'filters.airline': 'Airline',
    'filters.selectAirline': 'Select airline',
    'filters.allAirlines': 'All Airlines',
    'filters.searchAirline': 'Search airline...',
    'filters.searchDestination': 'Search destination...',
    'filters.searchAirport': 'Search airport...',
    'filters.searchCountry': 'Search country...',
    'filters.searchCity': 'Search city...',
    'filters.airport': 'Airport',
    'filters.country': 'Country',
    'filters.city': 'City',
    'filters.all': 'All',
    'filters.topCount': 'Top/Bottom Count',
    'filters.noResults': 'No results found',
    
    // Airline Table
    'airline.name': 'Airline',
    'airline.performance': 'Performance',
    'airline.rating': 'Rating',
    'airline.delays': 'Delays',
    'airline.cancellations': 'Cancellations',
    'airline.onTime': 'On Time',
    'airline.avgDelay': 'Avg Delay (All)',
    'airline.minutes': 'min',
    'airline.flights': 'Flights',
    'airline.total': 'Total Airlines',
    'airline.totalFlights': 'Total Flights',
    'airline.avgOnTime': 'Avg On-Time Rate',
    'airline.top5': 'Top 5 Airlines',
    'airline.bottom5': 'Bottom 5 Airlines',
    'airline.topN': 'Top {count} Airlines',
    'airline.bottomN': 'Bottom {count} Airlines',
    'airline.destination': 'Destination',
    'airline.destinationsFor': 'Destinations for',
    
    // Common
    'common.loading': 'Loading...',
    'common.error': 'Error',
    'common.retry': 'Retry',
    'common.search': 'Search',
    'common.filter': 'Filter',
    'common.clear': 'Clear',
    'common.apply': 'Apply',
    'common.cancel': 'Cancel',
    'common.save': 'Save',
    'common.edit': 'Edit',
    'common.delete': 'Delete',
    'common.close': 'Close',
    
    // 404 Page
    'notFound.message': 'Oops! Page not found',
    'notFound.returnHome': 'Return to Home',
    
    // Database
    'database.connect': 'Connect to DB',
    'database.disconnect': 'Disconnect from DB',
    'database.noData': 'No data available',
    'database.error': 'Failed to connect to database',
    
    // Destination Search Hero
    'search.byDestination': 'Search by destination',
    'search.whereFlying': 'Where are you flying?',
    'search.placeholder': 'For example: London',
    'search.destinationPlaceholder': 'Search for a destination (e.g. Barcelona)',
    'search.popularDestinations': 'Popular destinations:',
    'search.or': 'OR',

    // AI natural-language search
    'ai.badge': 'AI',
    'ai.title': 'Ask the data',
    'ai.description': 'Ask questions in natural language about airlines, destinations, delays and cancellations.',
    'ai.placeholder': 'Which airline is the most reliable for Barcelona?',
    'ai.placeholderShort': 'Most reliable airline to Barcelona?',
    'ai.ask': 'Ask',
    'ai.basedOnOver': 'Based on over {count} flights',
    'ai.error': 'Network error. Please try again.',

    // Destination Performance Table
    'performance.tableTitle': 'Airline Performance to {city}',
    'performance.topTableTitle': 'Top 10 Airlines by On-Time Performance',
    'performance.totalFlights': 'Total Flights',
    'performance.onTimePct': 'On Time %',
    'performance.cancelledPct': 'Cancelled %',
    'performance.avgDelay': 'Avg Delay',
    'performance.minutes': 'min',
    'performance.noResults': 'No data found for this destination',
    'performance.selectCity': 'Search for a destination to see airline performance',

    // Overview stats
    'stats.flights': 'Flights',
    'stats.departures': 'Departures',
    'stats.arrivals': 'Arrivals',
    'stats.total': 'Total Flights',
    'stats.airlines': 'Airlines',
    'stats.destinations': 'Destinations',

    // Flights Table
    'flights.title': 'Historical Flight Data',
    'flights.direction': 'Direction',
    'flights.airline': 'Airline',
    'flights.flight': 'Flight',
    'flights.destination': 'Destination',
    'flights.scheduled': 'Scheduled',
    'flights.actual': 'Actual',
    'flights.status': 'Status',
    'flights.delay': 'Delay',
    'flights.terminal': 'Terminal',
    'flights.minutes': 'min',
    'flights.onTime': 'On Time',

    // Live Flight Board
    'board.liveBoard': 'Live Flight Board',
    'board.title': 'Flight Board',
    'board.airport': 'Ben Gurion Airport',
    'board.arrivals': 'Arrivals',
    'board.departures': 'Departures',
    'board.flightNumber': 'Flight number',
    'board.airline': 'Airline',
    'board.city': 'City',
    'board.terminal': 'Terminal',
    'board.fromDate': 'From date',
    'board.toDate': 'To date',
    'board.search': 'Search',
    'board.clear': 'Clear',
    'board.allAirlines': 'All Airlines',
    'board.allCities': 'All Cities',
    'board.allTerminals': 'All Terminals',
    'board.lastUpdated': 'Last updated at',
    'board.pauseRefresh': 'Pause auto refresh',
    'board.resumeRefresh': 'Resume auto refresh',
    'board.backToDashboard': 'Back to Dashboard',
    'board.col.airline': 'Airline',
    'board.col.flight': 'Flight',
    'board.col.from': 'From',
    'board.col.to': 'To',
    'board.col.terminal': 'Terminal',
    'board.col.scheduled': 'Scheduled',
    'board.col.updated': 'Updated',
    'board.col.status': 'Status',
    'board.noFlights': 'No flights found',
    'board.connecting': 'Connecting to live feed...',
    'board.page': 'Page',
    'board.of': 'of',
    'board.prev': 'Previous',
    'board.next': 'Next',
    'board.status.landed': 'Landed',
    'board.status.arriving': 'Arriving',
    'board.status.final': 'Final',
    'board.status.cancelled': 'Cancelled',
    'board.status.delayed': 'Delayed',
    'board.status.onTime': 'On Time',
    'board.status.departed': 'Departed',
    'board.status.boarding': 'Boarding',
    'board.status.gateOpen': 'Gate Open',
    'board.status.gateClose': 'Gate Closed',
    'board.status.taxiing': 'Taxiing',

    // Insights page
    'insights.title': 'Insights',
    'insights.subtitle': 'What the flight data shows once you stop looking at one airline at a time',
    'insights.dow.sun': 'Sun',
    'insights.dow.mon': 'Mon',
    'insights.dow.tue': 'Tue',
    'insights.dow.wed': 'Wed',
    'insights.dow.thu': 'Thu',
    'insights.dow.fri': 'Fri',
    'insights.dow.sat': 'Sat',
    'insights.israeli': 'Israeli carriers',
    'insights.foreign': 'Foreign carriers',
    'insights.scheduled': 'Scheduled departures',
    'insights.cancelledPct': 'Cancelled %',
    'insights.onTimePct': 'On-time %',
    'insights.flights': 'Flights',
    'insights.crisisLabel': 'Disruption',

    'insights.sky.title': 'When the sky closed',
    'insights.sky.body': 'Foreign and Israeli airlines reacted in completely different ways. In {crisisStart} foreign carriers cancelled {foreignCancel} of the flights they had planned, against {israeliCancel} for Israeli carriers. By {crisisEnd} the foreign airlines had all but stopped flying to Israel — just {foreignApril} departures, against {foreignBaseline} two months earlier. The Israeli airlines kept flying: {israeliApril} departures that same month.',
    'insights.sky.caption': 'Scheduled departures per month, stacked by carrier nationality. The line is the cancellation rate across all carriers. The shaded band is derived from the data, not fixed in code: a month is flagged when its cancellation rate exceeds both 5% and three times the calm-month median.',

    'insights.shabbat.title': 'Shabbat is the best day to fly',
    'insights.shabbat.body': 'Saturday departures run {satPct} on time — far ahead of every other day, and roughly {gap} points better than the worst. Fewer flights means less congestion, and the schedule is built around it.',
    'insights.shabbat.caption': 'On-time share of operated departures by weekday. On time means departing within 15 minutes of schedule. Cancelled flights are excluded.',

    'insights.wall.title': 'The late-afternoon wall',
    'insights.wall.body': 'Punctuality decays across the day. Departures scheduled at {worstHour}:00 run {worstPct} on time, against {bestPct} at {bestHour}:00. Delay accumulates through the day and does not clear until the night bank.',
    'insights.wall.caption': 'On-time share of operated departures by scheduled hour. Cancelled flights are excluded.',

    'insights.share.title': 'The blue-and-white shift',
    'insights.share.body': 'Israeli carriers flew {shareBefore} of departures before the disruption. During it they carried almost everything, and they have kept a larger share since — {shareNow} in the most recent month.',
    'insights.share.caption': 'Israeli carriers as a share of all scheduled departures each month.',

    // Recovery page
    'recovery.title': "Who's flying again",
    'recovery.subtitle': 'Every carrier measured against its own pre-disruption baseline, recalculated on each update',
    'recovery.bucket.never_returned': 'Never came back',
    'recovery.bucket.partial': 'Partly back',
    'recovery.bucket.recovered': 'Fully recovered',
    'recovery.bucket.expanded': 'Flying more than before',
    'recovery.bucket.never_returned.hint': 'No departures in the last 30 days',
    'recovery.bucket.partial.hint': 'Below 90% of their pre-crisis baseline',
    'recovery.bucket.recovered.hint': '90–125% of their pre-crisis baseline',
    'recovery.bucket.expanded.hint': 'Above 125% — expanded into the gap',
    'recovery.timeline.title': 'When each carrier came back',
    'recovery.timeline.caption': 'First departure operated after a stoppage of at least 14 days. Carriers that never stopped flying have no return date and are not plotted.',
    'recovery.stillGone.title': 'Still missing',
    'recovery.table.title': 'All carriers',
    'recovery.table.carrier': 'Carrier',
    'recovery.table.baseline': 'Before (per month)',
    'recovery.table.last30': 'Last 30 days',
    'recovery.table.recovery': 'Recovery',
    'recovery.table.returned': 'Came back',
    'recovery.table.status': 'Status',
    'recovery.neverStopped': 'Never stopped',
    'recovery.filter.all': 'All',
    'recovery.methodology': 'Baseline is each carrier’s own average monthly operated departures from {start} to {end}. A carrier counts as back only if it operated departures in the last 30 days — a single flight followed by silence does not count.',
    'recovery.noData': 'No disruption found in the current data, so there is no recovery to report.',

    // Airlines page
    'airlines.title': 'Airline Performance',
    'airlines.subtitle': 'Pick an airline to see how it performs overall — and on every route it flies',
    'airlines.searchPlaceholder': 'Which airline?',
    'airlines.popular': 'Common:',
    'airlines.empty': 'Search for an airline above to see its full record',
    'airlines.notFound': 'No departures found for this airline',
    'airlines.kpi.flights': 'Departures',
    'airlines.kpi.onTime': 'On time',
    'airlines.kpi.cancelled': 'Cancelled',
    'airlines.kpi.avgDelay': 'Avg delay when late',
    'airlines.kpi.destinations': 'Destinations',
    'airlines.kpi.worstDelay': 'Worst delay',
    'airlines.ownAverage': 'Its own average',
    'airlines.minutes': 'min',

    'airlines.profile.title': 'How late, when late',
    'airlines.profile.caption': 'Every departure this airline scheduled, split by how far from schedule it left. On time means within 15 minutes. A low on-time share matters less if the delays are short — this shows which kind of airline it is.',
    'airlines.profile.early': 'Early',
    'airlines.profile.onTime': 'On time (0–15)',
    'airlines.profile.late': 'Late (15–60)',
    'airlines.profile.veryLate': 'Very late (60+)',
    'airlines.profile.cancelled': 'Cancelled',

    'airlines.trend.title': 'Its record over time',
    'airlines.trend.caption': 'Monthly on-time share for this airline. The dashed line is its own overall average across the whole period.',

    'airlines.routes.title': 'Performance by destination',
    'airlines.routes.caption': 'Every route this airline flies, measured the same way as the rest of the site. "vs its own average" compares each route against this airline’s overall on-time share — not against other airlines.',
    'airlines.routes.search': 'Filter destinations...',
    'airlines.routes.destination': 'Destination',
    'airlines.routes.flights': 'Flights',
    'airlines.routes.onTime': 'On time',
    'airlines.routes.vsOwn': 'vs its own average',
    'airlines.routes.cancelled': 'Cancelled',
    'airlines.routes.avgDelay': 'Avg delay',
    'airlines.routes.best': 'Best route',
    'airlines.routes.worst': 'Worst route',
    'airlines.routes.minFlights': 'Only routes with {n}+ flights',
    'airlines.routes.none': 'No routes match',
  },
  he: {
    // Navigation
    'nav.dashboard': 'לוח בקרה',
    'nav.airlines': 'חברות תעופה',
    'nav.settings': 'הגדרות',
    'nav.rankings': 'דירוגים',
    'nav.airlinePerformance': 'ביצועי חברות',
    'nav.insights': 'תובנות',
    'nav.recovery': 'מי חזר לטוס',
    'nav.flightBoard': 'לוח טיסות',
    'nav.primary': 'ניווט ראשי',

    // Theme
    'theme.toggle': 'החלף ערכת נושא',
    'theme.light': 'בהיר',
    'theme.dark': 'כהה',
    
    // Language
    'language.toggle': 'החלף שפה',
    'language.english': 'English',
    'language.hebrew': 'עברית',
    
    // Dashboard
    'dashboard.title': 'RankAir – השוואת ביצועי חברות תעופה בנתב״ג',
    'dashboard.subtitle.line1': 'בדקו איזו חברה עומדת בזמנים לפני שמזמינים, כולל מידע על ביטולים',
    'dashboard.subtitle.line2': 'מבוסס על נתוני טיסות מרשות שדות התעופה, המתעדכנים כל 15 דקות ונאספים לאורך זמן',
    'dashboard.filters': 'מסננים',
    'dashboard.search': 'חיפוש חברות תעופה...',
    
    // Filters
    'filters.destination': 'יעד',
    'filters.selectDestination': 'בחר יעד',
    'filters.allDestinations': 'כל היעדים',
    'filters.dateRange': 'טווח תאריכים',
    'filters.allTime': 'כל הזמנים',
    'filters.last7Days': '7 הימים האחרונים',
    'filters.last30Days': '30 הימים האחרונים',
    'filters.last90Days': '90 הימים האחרונים',
    'filters.lastYear': 'השנה האחרונה',
    'filters.dayOfWeek': 'יום בשבוע',
    'filters.allDays': 'כל הימים',
    'filters.monday': 'יום שני',
    'filters.tuesday': 'יום שלישי',
    'filters.wednesday': 'יום רביעי',
    'filters.thursday': 'יום חמישי',
    'filters.friday': 'יום שישי',
    'filters.saturday': 'יום שבת',
    'filters.sunday': 'יום ראשון',
    'filters.airline': 'חברת תעופה',
    'filters.selectAirline': 'בחר חברת תעופה',
    'filters.allAirlines': 'כל חברות התעופה',
    'filters.searchAirline': 'חפש חברת תעופה...',
    'filters.searchDestination': 'חפש יעד...',
    'filters.searchAirport': 'חפש שדה תעופה...',
    'filters.airport': 'שדה תעופה',
    'filters.all': 'הכל',
    'filters.topCount': 'כמות מובילים/נמוכים',
    'filters.noResults': 'לא נמצאו תוצאות',
    
    // Airline Table
    'airline.name': 'חברת תעופה',
    'airline.performance': 'ביצועים',
    'airline.rating': 'דירוג',
    'airline.delays': 'עיכובים',
    'airline.cancellations': 'ביטולים',
    'airline.onTime': 'בזמן',
    'airline.avgDelay': 'עיכוב ממוצע (כל הטיסות)',
    'airline.minutes': 'דקות',
    'airline.flights': '# טיסות',
    'airline.total': 'סה"כ חברות תעופה',
    'airline.totalFlights': 'סה"כ טיסות',
    'airline.avgOnTime': 'אחוז בזמן ממוצע',
    'airline.top5': '5 החברות הטובות',
    'airline.bottom5': '5 החברות הגרועות',
    'airline.topN': 'חברות התעופה המובילות {count}',
    'airline.bottomN': 'חברות התעופה בתחתית {count}',
    'airline.destination': 'יעד',
    'airline.destinationsFor': 'יעדים עבור',
    
    // Common
    'common.loading': 'טוען...',
    'common.error': 'שגיאה',
    'common.retry': 'נסה שוב',
    'common.search': 'חיפוש',
    'common.filter': 'סנן',
    'common.clear': 'נקה',
    'common.apply': 'החל',
    'common.cancel': 'בטל',
    'common.save': 'שמור',
    'common.edit': 'ערוך',
    'common.delete': 'מחק',
    'common.close': 'סגור',
    
    // 404 Page
    'notFound.message': 'אופס! הדף לא נמצא',
    'notFound.returnHome': 'חזור לעמוד הבית',
    
    // Database
    'database.connect': 'התחבר למסד נתונים',
    'database.disconnect': 'נתק ממסד נתונים',
    'database.noData': 'אין נתונים זמינים',
    'database.error': 'נכשל בחיבור למסד הנתונים',
    
    // Destination Search Hero
    'search.byDestination': 'חיפוש לפי יעד',
    'search.whereFlying': 'לאן אתם טסים?',
    'search.placeholder': 'לדוגמה: לונדון',
    'search.destinationPlaceholder': 'חפשו יעד (לדוגמה: ברצלונה)',
    'search.popularDestinations': 'יעדים פופולריים:',
    'search.or': 'או',

    // AI natural-language search
    'ai.badge': 'AI',
    'ai.title': 'שאלו את הנתונים',
    'ai.description': 'שאלו שאלות בשפה חופשית על חברות תעופה, יעדים, עיכובים וביטולים.',
    'ai.placeholder': 'איזו חברת תעופה הכי אמינה לברצלונה?',
    'ai.placeholderShort': 'החברה הכי אמינה לברצלונה?',
    'ai.ask': 'שאלו',
    'ai.basedOnOver': 'מבוסס על יותר מ-{count} טיסות',
    'ai.error': 'שגיאת רשת. נסו שוב.',

    // Destination Performance Table
    'performance.tableTitle': 'ביצועי חברות תעופה ל{city}',
    'performance.topTableTitle': '10 חברות התעופה הכי מדויקות',
    'performance.totalFlights': 'סה"כ טיסות',
    'performance.onTimePct': '% בזמן',
    'performance.cancelledPct': '% ביטולים',
    'performance.avgDelay': 'עיכוב ממוצע',
    'performance.minutes': 'דקות',
    'performance.noResults': 'לא נמצאו נתונים עבור יעד זה',
    'performance.selectCity': 'חפשו יעד כדי לראות ביצועי חברות תעופה',

    // Overview stats
    'stats.flights': 'טיסות',
    'stats.departures': 'המראות',
    'stats.arrivals': 'נחיתות',
    'stats.total': 'סה"כ טיסות',
    'stats.airlines': 'חברות תעופה',
    'stats.destinations': 'יעדים',

    // Flights Table
    'flights.title': 'נתוני טיסות היסטוריים',
    'flights.direction': 'כיוון',
    'flights.airline': 'חברת תעופה',
    'flights.flight': 'טיסה',
    'flights.destination': 'יעד',
    'flights.scheduled': 'מתוכנן',
    'flights.actual': 'מעשי',
    'flights.status': 'סטטוס',
    'flights.delay': 'עיכוב',
    'flights.terminal': 'טרמינל',
    'flights.minutes': 'דקות',
    'flights.onTime': 'בזמן',

    // Live Flight Board
    'board.liveBoard': 'לוח טיסות מתעדכן',
    'board.title': 'לוח טיסות',
    'board.airport': 'נמל תעופה בן גוריון',
    'board.arrivals': 'נחיתות',
    'board.departures': 'המראות',
    'board.flightNumber': 'מספר טיסה',
    'board.airline': 'חברת תעופה',
    'board.city': 'עיר',
    'board.terminal': 'טרמינל',
    'board.fromDate': 'מתאריך',
    'board.toDate': 'עד תאריך',
    'board.search': 'חפש',
    'board.clear': 'נקה',
    'board.allAirlines': 'כל חברות התעופה',
    'board.allCities': 'כל הערים',
    'board.allTerminals': 'כל הטרמינלים',
    'board.lastUpdated': 'עדכון אחרון בוצע ב-',
    'board.pauseRefresh': 'עצור עדכון אוטומטי',
    'board.resumeRefresh': 'חדש עדכון אוטומטי',
    'board.backToDashboard': 'חזור ללוח הבקרה',
    'board.col.airline': 'חברת תעופה',
    'board.col.flight': 'טיסה',
    'board.col.from': 'מוצא',
    'board.col.to': 'יעד',
    'board.col.terminal': 'טרמינל',
    'board.col.scheduled': 'זמן מתוכנן',
    'board.col.updated': 'זמן עדכני',
    'board.col.status': 'סטטוס',
    'board.noFlights': 'לא נמצאו טיסות',
    'board.connecting': 'מתחבר לעדכון חי...',
    'board.page': 'עמוד',
    'board.of': 'מתוך',
    'board.prev': 'הקודם',
    'board.next': 'הבא',
    'board.status.landed': 'נחתה',
    'board.status.arriving': 'בנחיתה',
    'board.status.final': 'סופי',
    'board.status.cancelled': 'בוטלה',
    'board.status.delayed': 'התעכבה',
    'board.status.onTime': 'בזמן',
    'board.status.departed': 'המריאה',
    'board.status.boarding': 'עלייה למטוס',
    'board.status.gateOpen': 'שער פתוח',
    'board.status.gateClose': 'שער סגור',
    'board.status.taxiing': 'נוסע לשביל',

    // Insights page
    'insights.title': 'תובנות',
    'insights.subtitle': 'מה שנתוני הטיסות מראים כשמפסיקים להסתכל על חברה אחת בכל פעם',
    'insights.dow.sun': 'ראשון',
    'insights.dow.mon': 'שני',
    'insights.dow.tue': 'שלישי',
    'insights.dow.wed': 'רביעי',
    'insights.dow.thu': 'חמישי',
    'insights.dow.fri': 'שישי',
    'insights.dow.sat': 'שבת',
    'insights.israeli': 'חברות ישראליות',
    'insights.foreign': 'חברות זרות',
    'insights.scheduled': 'המראות מתוכננות',
    'insights.cancelledPct': '% ביטולים',
    'insights.onTimePct': '% בזמן',
    'insights.flights': 'טיסות',
    'insights.crisisLabel': 'תקופת המשבר',

    'insights.sky.title': 'כשהשמיים נסגרו',
    'insights.sky.body': 'החברות הזרות והישראליות הגיבו אחרת לגמרי. ב{crisisStart} החברות הזרות ביטלו {foreignCancel} מהטיסות שתכננו, לעומת {israeliCancel} בחברות הישראליות. עד {crisisEnd} החברות הזרות כמעט הפסיקו לטוס לישראל — {foreignApril} המראות בלבד, לעומת {foreignBaseline} חודשיים קודם. החברות הישראליות המשיכו לטוס: {israeliApril} המראות באותו חודש.',
    'insights.sky.caption': 'המראות מתוכננות בכל חודש, מחולקות לפי לאום החברה. הקו מציג את שיעור הביטולים בכלל החברות. התחום המוצלל מחושב מהנתונים ולא קבוע בקוד: חודש מסומן כאשר שיעור הביטולים בו עולה גם על 5% וגם על פי שלושה מהחציון של החודשים הרגועים.',

    'insights.shabbat.title': 'שבת זה היום הכי טוב לטוס',
    'insights.shabbat.body': 'המראות בשבת יוצאות בזמן ב-{satPct} מהמקרים — הרבה מעל כל יום אחר, ובפער של כ-{gap} נקודות מהיום הגרוע ביותר. פחות טיסות פירושן פחות עומס, והלוח בנוי סביב זה.',
    'insights.shabbat.caption': 'שיעור ההמראות שיצאו בזמן לפי יום בשבוע. "בזמן" הוא יציאה עד 15 דקות מהמועד המתוכנן. טיסות שבוטלו אינן נכללות.',

    'insights.wall.title': 'הקיר של אחר הצהריים',
    'insights.wall.body': 'הדייקנות נשחקת במהלך היום. המראות שתוכננו ל-{worstHour}:00 יוצאות בזמן ב-{worstPct} מהמקרים, לעומת {bestPct} ב-{bestHour}:00. העיכוב מצטבר לאורך היום ולא מתפוגג עד הגל הלילי.',
    'insights.wall.caption': 'שיעור ההמראות שיצאו בזמן לפי שעת ההמראה המתוכננת. טיסות שבוטלו אינן נכללות.',

    'insights.share.title': 'התזוזה הכחול-לבן',
    'insights.share.body': 'לפני המשבר החברות הישראליות הפעילו {shareBefore} מההמראות. במהלכו הן נשאו כמעט הכול, ומאז הן שומרות על נתח גדול יותר — {shareNow} בחודש האחרון.',
    'insights.share.caption': 'נתח החברות הישראליות מכלל ההמראות המתוכננות בכל חודש.',

    // Recovery page
    'recovery.title': 'מי חזר לטוס',
    'recovery.subtitle': 'כל חברה נמדדת מול הממוצע החודשי שלה מלפני המשבר, בחישוב מחדש בכל עדכון',
    'recovery.bucket.never_returned': 'לא חזרו',
    'recovery.bucket.partial': 'חזרו חלקית',
    'recovery.bucket.recovered': 'חזרו במלואן',
    'recovery.bucket.expanded': 'טסות יותר מקודם',
    'recovery.bucket.never_returned.hint': 'ללא המראות ב-30 הימים האחרונים',
    'recovery.bucket.partial.hint': 'מתחת ל-90% מהממוצע שלפני המשבר',
    'recovery.bucket.recovered.hint': '90%–125% מהממוצע שלפני המשבר',
    'recovery.bucket.expanded.hint': 'מעל 125% — התרחבו לתוך החלל שנוצר',
    'recovery.timeline.title': 'מתי כל חברה חזרה',
    'recovery.timeline.caption': 'ההמראה הראשונה שבוצעה אחרי הפסקה של 14 יום לפחות. חברות שלא הפסיקו לטוס אינן מקבלות תאריך חזרה ואינן מוצגות בציר.',
    'recovery.stillGone.title': 'עדיין חסרות',
    'recovery.table.title': 'כל החברות',
    'recovery.table.carrier': 'חברת תעופה',
    'recovery.table.baseline': 'קודם (לחודש)',
    'recovery.table.last30': '30 ימים אחרונים',
    'recovery.table.recovery': 'החזרה',
    'recovery.table.returned': 'תאריך חזרה',
    'recovery.table.status': 'סטטוס',
    'recovery.neverStopped': 'לא הפסיקו',
    'recovery.filter.all': 'הכל',
    'recovery.methodology': 'בסיס ההשוואה הוא ממוצע ההמראות החודשי של כל חברה בעצמה מ-{start} עד {end}. חברה נחשבת כמי שחזרה רק אם ביצעה המראות ב-30 הימים האחרונים — טיסה בודדת ואחריה שקט אינה נחשבת.',
    'recovery.noData': 'לא נמצא משבר בנתונים הנוכחיים, ולכן אין חזרה לדווח עליה.',

    // Airlines page
    'airlines.title': 'ביצועי חברות תעופה',
    'airlines.subtitle': 'בחרו חברת תעופה כדי לראות איך היא מתפקדת בסך הכול — ובכל יעד שאליו היא טסה',
    'airlines.searchPlaceholder': 'איזו חברת תעופה?',
    'airlines.popular': 'נפוצות:',
    'airlines.empty': 'חפשו חברת תעופה למעלה כדי לראות את התמונה המלאה שלה',
    'airlines.notFound': 'לא נמצאו המראות עבור חברה זו',
    'airlines.kpi.flights': 'המראות',
    'airlines.kpi.onTime': 'בזמן',
    'airlines.kpi.cancelled': 'בוטלו',
    'airlines.kpi.avgDelay': 'עיכוב ממוצע באיחור',
    'airlines.kpi.destinations': 'יעדים',
    'airlines.kpi.worstDelay': 'העיכוב הגרוע ביותר',
    'airlines.ownAverage': 'הממוצע שלה עצמה',
    'airlines.minutes': 'דק׳',

    'airlines.profile.title': 'כמה מאחרת, כשמאחרת',
    'airlines.profile.caption': 'כל ההמראות שהחברה תכננה, לפי מרחקן מהמועד המתוכנן. "בזמן" הוא עד 15 דקות. אחוז נמוך של טיסות בזמן פחות חמור אם העיכובים קצרים — כאן רואים באיזו חברה מדובר.',
    'airlines.profile.early': 'מוקדם',
    'airlines.profile.onTime': 'בזמן (0–15)',
    'airlines.profile.late': 'באיחור (15–60)',
    'airlines.profile.veryLate': 'באיחור כבד (60+)',
    'airlines.profile.cancelled': 'בוטלו',

    'airlines.trend.title': 'הביצועים שלה לאורך זמן',
    'airlines.trend.caption': 'אחוז הטיסות בזמן בכל חודש עבור החברה הזו. הקו המקווקו הוא הממוצע שלה עצמה לאורך כל התקופה.',

    'airlines.routes.title': 'ביצועים לפי יעד',
    'airlines.routes.caption': 'כל היעדים שאליהם החברה טסה, נמדדים באותה שיטה כמו בשאר האתר. "מול הממוצע שלה" משווה כל יעד לאחוז הטיסות בזמן של החברה הזו עצמה — ולא לחברות אחרות.',
    'airlines.routes.search': 'סינון יעדים...',
    'airlines.routes.destination': 'יעד',
    'airlines.routes.flights': 'טיסות',
    'airlines.routes.onTime': 'בזמן',
    'airlines.routes.vsOwn': 'מול הממוצע שלה',
    'airlines.routes.cancelled': 'בוטלו',
    'airlines.routes.avgDelay': 'עיכוב ממוצע',
    'airlines.routes.best': 'היעד הטוב ביותר',
    'airlines.routes.worst': 'היעד הגרוע ביותר',
    'airlines.routes.minFlights': 'רק יעדים עם {n}+ טיסות',
    'airlines.routes.none': 'אין יעדים תואמים',
  }
};

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguage] = useState<Language>('he');

  // Load language from localStorage on mount
  useEffect(() => {
    const savedLanguage = localStorage.getItem('language') as Language;
    if (savedLanguage && (savedLanguage === 'en' || savedLanguage === 'he')) {
      setLanguage(savedLanguage);
    }
  }, []);

  // Save language to localStorage when it changes
  useEffect(() => {
    localStorage.setItem('language', language);
    // Update document direction for RTL support
    document.documentElement.dir = language === 'he' ? 'rtl' : 'ltr';
    document.documentElement.lang = language;
  }, [language]);

  const t = (key: string): string => {
    return translations[language][key as keyof typeof translations[typeof language]] || key;
  };

  const isRTL = language === 'he';

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t, isRTL }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => {
  const context = useContext(LanguageContext);
  if (context === undefined) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};
