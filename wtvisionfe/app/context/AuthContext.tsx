// c:\Users\ritam\wtvision\wtvisionfe\app\context\AuthContext.tsx
'use client';

import React, { createContext, useState, useContext, ReactNode } from 'react';

interface User {
    id: string;
    email: string;
    role?: string;
    username?: string;
}

interface AuthState {
    user: User | null;
    accessToken: string | null;
}

interface AuthContextType {
    auth: AuthState;
    setAuth: React.Dispatch<React.SetStateAction<AuthState>>;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
    const [auth, setAuth] = useState<AuthState>({
        user: null,
        accessToken: null,
    });

    const logout = () => {
        setAuth({ user: null, accessToken: null });
    };

    return (
        <AuthContext.Provider value={{ auth, setAuth, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
