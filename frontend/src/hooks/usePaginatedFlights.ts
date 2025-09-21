import { useState, useEffect } from 'react';

interface PaginationInfo {
  page: number;
  size: number;
  total: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}

interface Flight {
  flight_id: string;
  airline_code: string;
  flight_number: string;
  direction: string;
  location_iata: string;
  scheduled_time: string;
  actual_time: string | null;
  airline_name: string;
  location_en: string;
  location_he: string;
  location_city_en: string;
  country_en: string;
  country_he: string;
  terminal: string | null;
  checkin_counters: string | null;
  checkin_zone: string | null;
  status_en: string;
  status_he: string;
  delay_minutes: number;
  scrape_timestamp: string | null;
  raw_s3_path: string;
}

interface UsePaginatedFlightsResult {
  data: Flight[];
  pagination: PaginationInfo | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
  goToPage: (page: number) => void;
  changePageSize: (size: number) => void;
  sortBy: (field: string) => void;
  currentPage: number;
  pageSize: number;
  sortField: string;
  sortDirection: 'asc' | 'desc';
}

export const usePaginatedFlights = (baseUrl: string): UsePaginatedFlightsResult => {
  const [data, setData] = useState<Flight[]>([]);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [sortField, setSortField] = useState('scheduled_time');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  const fetchData = async (page: number = currentPage, size: number = pageSize, sort: string = sortField, order: string = sortDirection) => {
    setLoading(true);
    setError(null);
    
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        size: size.toString(),
        sort_by: sort,
        sort_order: order
      });
      
      const response = await fetch(`${baseUrl}?${params}`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json();
      
      if (result.data && Array.isArray(result.data)) {
        setData(result.data);
        setPagination(result.pagination);
        setCurrentPage(page);
      } else {
        throw new Error('Invalid response format');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred';
      setError(`Failed to fetch data: ${errorMessage}`);
      setData([]);
      setPagination(null);
    } finally {
      setLoading(false);
    }
  };

  const goToPage = (page: number) => {
    if (pagination && page >= 1 && page <= pagination.pages) {
      fetchData(page, pageSize, sortField, sortDirection);
    }
  };

  const changePageSize = (size: number) => {
    setPageSize(size);
    fetchData(1, size, sortField, sortDirection);
  };

  const sortBy = (field: string) => {
    const newDirection = field === sortField && sortDirection === 'desc' ? 'asc' : 'desc';
    setSortField(field);
    setSortDirection(newDirection);
    fetchData(1, pageSize, field, newDirection);
  };

  useEffect(() => {
    if (baseUrl) {
      fetchData();
    }
  }, [baseUrl]);

  return {
    data,
    pagination,
    loading,
    error,
    refetch: () => fetchData(currentPage, pageSize, sortField, sortDirection),
    goToPage,
    changePageSize,
    sortBy,
    currentPage,
    pageSize,
    sortField,
    sortDirection
  };
};

