import React, { useEffect, useState } from 'react';
import { index } from './api/sdk.gen';
import { HelloView } from './api/types.gen';
import HelloComponent from './components/Hello';

const App: React.FC = () => {
  const [helloData, setHelloData] = useState<HelloView | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchHelloData = async () => {
      try {
        setLoading(true);
        const startTime = Date.now();

        // Fetch data from API
        const result = await index();

        // Check if result contains data or error
        if ('error' in result && result.error) {
          setError(`API Error: ${JSON.stringify(result.error)}`);
          setHelloData(null);
        } else if ('data' in result && result.data) {
          setHelloData(result.data);
          setError(null);
        } else {
          setError('Received empty response from API');
          setHelloData(null);
        }

        // Calculate how much time has passed
        const elapsedTime = Date.now() - startTime;

        // If less than 500ms has passed, wait until 500ms total has elapsed
        if (elapsedTime < 500) {
          await new Promise(resolve => setTimeout(resolve, 500 - elapsedTime));
        }
      } catch (err) {
        console.error('Failed to fetch hello data:', err);
        setError('Failed to load data from API');
      } finally {
        setLoading(false);
      }
    };

    fetchHelloData();
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-md mx-auto">
        <h1 className="text-2xl font-bold mb-6 text-gray-800">Example App</h1>

        <div className="bg-white p-6 rounded-lg shadow-md">
          {loading ? (
            <div className="py-4 text-center text-gray-500">Loading...</div>
          ) : error ? (
            <div className="py-4 text-center text-red-500">{error}</div>
          ) : helloData ? (
            <HelloComponent data={helloData} />
          ) : (
            <div className="py-4 text-center text-gray-500">No data available</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default App;
