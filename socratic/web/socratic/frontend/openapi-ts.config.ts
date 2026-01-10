import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  input: 'http://localhost:8089/openapi.json',
  output: 'src/api',
  plugins: [
    '@hey-api/typescript',
    {
      name: '@hey-api/sdk',
      client: '@hey-api/client-fetch',
    },
  ],
});
