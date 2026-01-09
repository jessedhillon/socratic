import React from 'react';
import { HelloView } from '../api/types.gen';

interface HelloComponentProps {
  data: HelloView;
}

const HelloComponent: React.FC<HelloComponentProps> = ({ data }) => {
  const getEnvColor = (env: HelloView['env']) => {
    switch (env) {
      case 'production':
        return 'bg-red-500';
      case 'staging':
        return 'bg-orange-500';
      case 'development':
        return 'bg-blue-500';
      case 'sandbox':
        return 'bg-purple-500';
      case 'test':
        return 'bg-yellow-500';
      case 'local':
      default:
        return 'bg-green-500';
    }
  };

  return (
    <div className="border border-gray-300 rounded-md overflow-hidden shadow-sm">
      {/* Header section with environment */}
      <div
        className={`${getEnvColor(data.env)} px-4 py-2 text-white font-medium`}
      >
        Environment: {data.env}
      </div>

      {/* Message content */}
      <div className="p-4 bg-white">{data.message}</div>
    </div>
  );
};

export default HelloComponent;
