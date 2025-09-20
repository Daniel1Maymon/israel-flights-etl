import { useState, useEffect } from 'react';

interface UseApiDataResult {
  data: any[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export const useApiData = (endpoint: string): UseApiDataResult => {
  const [data, setData] = useState<any[]>([]);
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
      
      const result = await response.json();
      
      // Handle both array and object responses
      if (Array.isArray(result)) {
        setData(result);
      } else if (result.data && Array.isArray(result.data)) {
        setData(result.data);
      } else if (result.flights && Array.isArray(result.flights)) {
        setData(result.flights);
      } else {
        // If it's an object, convert it to an array
        setData([result]);
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
  }, [endpoint]);

  return {
    data,
    loading,
    error,
    refetch: fetchData
  };
};
