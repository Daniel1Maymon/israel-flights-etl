import { useState, useEffect } from 'react';

interface UseApiDataResult<T = any> {
  data: T[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export const useApiData = <T = any>(endpoint: string): UseApiDataResult<T> => {
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(endpoint);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json() as any;
      
      // Handle both array and object responses
      if (Array.isArray(result)) {
        setData(result as T[]);
      } else if (result.data && Array.isArray(result.data)) {
        setData(result.data as T[]);
      } else if (result.flights && Array.isArray(result.flights)) {
        setData(result.flights as T[]);
      } else if (result.airlines && Array.isArray(result.airlines)) {
        setData(result.airlines as T[]);
      } else if (result.destinations && Array.isArray(result.destinations)) {
        setData(result.destinations as T[]);
      } else if (result.countries && Array.isArray(result.countries)) {
        setData(result.countries as T[]);
      } else {
        // If it's an object, convert it to an array
        setData([result as T]);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred';
      setError(`Failed to fetch data: ${errorMessage}`);
      setData([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (endpoint) {
      fetchData();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint]);

  return {
    data,
    loading,
    error,
    refetch: fetchData
  };
};
