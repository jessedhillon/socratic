import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  input: 'http://localhost:8081/openapi.json',
  output: 'src/api',
  plugins: ['@hey-api/client-fetch'],
});
