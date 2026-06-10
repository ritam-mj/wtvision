import axios from 'axios';
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost';
const AUTH_URL = process.env.NEXT_PUBLIC_AUTH_URL || 'http://localhost:8001';
// Public instance for general endpoints
export default axios.create({
    baseURL: BASE_URL,
    headers: { 'Content-Type': 'application/json' },
});
// Private instance that will automatically receive access token headers via intercepts
export const axiosPrivate = axios.create({
    baseURL: BASE_URL,
    headers: { 'Content-Type': 'application/json' },
    withCredentials: true, // Crucial for receiving/sending HTTP-only cookies
});
// Instance pointing directly to the Auth Microservice
export const axiosAuth = axios.create({
    baseURL: AUTH_URL,
    headers: { 'Content-Type': 'application/json' },
    withCredentials: true,
});
