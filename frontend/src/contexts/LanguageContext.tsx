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
    
    // Theme
    'theme.toggle': 'Toggle theme',
    'theme.light': 'Light',
    'theme.dark': 'Dark',
    
    // Language
    'language.toggle': 'Toggle language',
    'language.english': 'English',
    'language.hebrew': 'עברית',
    
    // Dashboard
    'dashboard.title': 'Compare Airline Performance at TLV',
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
    'search.whereFlying': 'Where are you flying?',
    'search.placeholder': 'For example: London',
    'search.popularDestinations': 'Popular destinations:',

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
  },
  he: {
    // Navigation
    'nav.dashboard': 'לוח בקרה',
    'nav.airlines': 'חברות תעופה',
    'nav.settings': 'הגדרות',
    
    // Theme
    'theme.toggle': 'החלף ערכת נושא',
    'theme.light': 'בהיר',
    'theme.dark': 'כהה',
    
    // Language
    'language.toggle': 'החלף שפה',
    'language.english': 'English',
    'language.hebrew': 'עברית',
    
    // Dashboard
    'dashboard.title': 'השוואת ביצועי חברות תעופה בנתב״ג',
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
    'search.whereFlying': 'לאן אתם טסים?',
    'search.placeholder': 'לדוגמה: לונדון',
    'search.popularDestinations': 'יעדים פופולריים:',

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
