// c:\Users\ritam\wtvision\wtvisionfe\app\hooks\UseAxiosPrivate.tsx
'use client';

import { useEffect } from 'react';
import { axiosPrivate, axiosAuth } from '../api/axios';
import { useAuth } from '../context/AuthContext';

export const useAxiosPrivate = () => {
    const { auth, setAuth } = useAuth();

    useEffect(() => {
        // 1. Request interceptor: Inject the current access token to outbound requests
        const requestIntercept = axiosPrivate.interceptors.request.use(
            (config) => {
                if (!config.headers['Authorization'] && auth.accessToken) {
                    config.headers['Authorization'] = `Bearer ${auth.accessToken}`;
                }
                return config;
            },
            (error) => Promise.reject(error)
        );

        // 2. Response interceptor: Trap 401 errors to refresh access tokens seamlessly
        const responseIntercept = axiosPrivate.interceptors.response.use(
            (response) => response,
            async (error) => {
                const prevRequest = error?.config;

                // If 401 error occurs and we haven't already retried this request
                if (error?.response?.status === 401 && !prevRequest?.sent) {
                    prevRequest.sent = true;

                    try {
                        // Hit the auth microservice token refresh endpoint.
                        // The secure HTTP-only refresh token cookie is sent automatically.
                        const response = await axiosAuth.post('/auth/token/refresh/', {});
                        const newAccessToken = response.data.access;

                        // Update react authentication state
                        setAuth((prev) => ({
                            ...prev,
                            accessToken: newAccessToken,
                        }));

                        // Re-apply the new access token to the original request headers
                        prevRequest.headers['Authorization'] = `Bearer ${newAccessToken}`;
                        return axiosPrivate(prevRequest);
                    } catch (refreshError) {
                        // If the refresh token has also expired or is invalid, force user to re-login
                        setAuth({ user: null, accessToken: null });
                        return Promise.reject(refreshError);
                    }
                }
                return Promise.reject(error);
            }
        );

        // Clean up interceptors on unmount
        return () => {
            axiosPrivate.interceptors.request.eject(requestIntercept);
            axiosPrivate.interceptors.response.eject(responseIntercept);
        };
    }, [auth, setAuth]);

    return axiosPrivate;
};
