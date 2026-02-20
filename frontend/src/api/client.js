import axios from 'axios';

// In dev, use relative URL so Vite proxy forwards /api to the backend (avoids CORS/network errors)
const baseURL =
  import.meta.env.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : import.meta.env.DEV
      ? ''
      : 'http://localhost:8000';

const client = axios.create({
  baseURL,
});

export default client;
