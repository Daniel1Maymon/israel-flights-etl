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
    'dashboard.title': 'Airline Performance Tracker',
    'dashboard.subtitle': 'Historical airline data to help you choose the best flights',
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
    
    // Airline Table
    'airline.name': 'Airline',
    'airline.performance': 'Performance',
    'airline.rating': 'Rating',
    'airline.delays': 'Delays',
    'airline.cancellations': 'Cancellations',
    'airline.onTime': 'On Time',
    'airline.avgDelay': 'Avg Delay',
    'airline.minutes': 'min',
    'airline.flights': 'Flights',
    'airline.total': 'Total Airlines',
    'airline.totalFlights': 'Total Flights',
    'airline.avgOnTime': 'Avg On-Time Rate',
    'airline.top5': 'Top 5 Airlines',
    'airline.bottom5': 'Bottom 5 Airlines',
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
    'dashboard.title': 'מעקב ביצועי חברות תעופה',
    'dashboard.subtitle': 'נתונים היסטוריים של חברות תעופה לעזרה בבחירת הטיסות הטובות ביותר',
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
    
    // Airline Table
    'airline.name': 'חברת תעופה',
    'airline.performance': 'ביצועים',
    'airline.rating': 'דירוג',
    'airline.delays': 'עיכובים',
    'airline.cancellations': 'ביטולים',
    'airline.onTime': 'בזמן',
    'airline.avgDelay': 'עיכוב ממוצע',
    'airline.minutes': 'דקות',
    'airline.flights': '# טיסות',
    'airline.total': 'סה"כ חברות תעופה',
    'airline.totalFlights': 'סה"כ טיסות',
    'airline.avgOnTime': 'אחוז בזמן ממוצע',
    'airline.top5': '5 החברות הטובות',
    'airline.bottom5': '5 החברות הגרועות',
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
  }
};

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguage] = useState<Language>('en');

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

