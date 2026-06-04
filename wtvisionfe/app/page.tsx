// c:\Users\ritam\wtvision\wtvisionfe\app\page.tsx
'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useAuth } from './context/AuthContext';
import { useAxiosPrivate } from '@/app/hooks';

export default function Home() {
  const { auth, setAuth, logout } = useAuth();
  const axiosPrivate = useAxiosPrivate();

  const [apiResponse, setApiResponse] = useState<any>(null);
  const [apiError, setApiError] = useState<string>('');
  const [isCallingApi, setIsCallingApi] = useState(false);

  // Username update state
  const [newUsername, setNewUsername] = useState('');
  const [usernameSuccess, setUsernameSuccess] = useState('');
  const [usernameError, setUsernameError] = useState('');
  const [isUpdatingUsername, setIsUpdatingUsername] = useState(false);

  // Password update state
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [isUpdatingPassword, setIsUpdatingPassword] = useState(false);

  const handleTestSecureCall = async () => {
    setIsCallingApi(true);
    setApiError('');
    setApiResponse(null);

    try {
      // Hits the API Gateway path, which will authenticate at the edge 
      // and proxy down to wtvisionbe on port 8000
      const response = await axiosPrivate.get('/api/v1/dashboard/');
      setApiResponse(response.data);
    } catch (err: any) {
      console.error('Secure API Call Error:', err);
      if (err.response) {
        setApiError(`[Status ${err.response.status}] ${err.response.data?.detail || 'Gateway blocked the request.'}`);
      } else {
        setApiError('Unable to reach the API Gateway. Verify your Gateway is running on Port 80.');
      }
    } finally {
      setIsCallingApi(false);
    }
  };

  const handleUpdateUsername = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsUpdatingUsername(true);
    setUsernameSuccess('');
    setUsernameError('');

    try {
      const authUrl = process.env.NEXT_PUBLIC_AUTH_URL || 'http://localhost:8001';
      const response = await axiosPrivate.post(`${authUrl}/user/update/`, {
        new_username: newUsername,
      });

      setUsernameSuccess(response.data.message || 'Username updated successfully.');
      setNewUsername('');
      
      // Update global context with new username
      if (auth.user) {
        setAuth((prev: any) => ({
          ...prev,
          user: {
            ...prev.user,
            username: response.data.username,
          },
        }));
      }
    } catch (err: any) {
      console.error('Username update error:', err);
      if (err.response) {
        setUsernameError(err.response.data?.detail || 'Failed to update username.');
      } else {
        setUsernameError('Auth Microservice is unreachable.');
      }
    } finally {
      setIsUpdatingUsername(false);
    }
  };

  const handleUpdatePassword = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsUpdatingPassword(true);
    setPasswordSuccess('');
    setPasswordError('');

    if (newPassword !== confirmPassword) {
      setPasswordError('New passwords do not match.');
      setIsUpdatingPassword(false);
      return;
    }

    try {
      const authUrl = process.env.NEXT_PUBLIC_AUTH_URL || 'http://localhost:8001';
      const response = await axiosPrivate.post(`${authUrl}/user/update/`, {
        old_password: oldPassword,
        new_password: newPassword,
      });

      setPasswordSuccess(response.data.message || 'Password updated successfully.');
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      console.error('Password update error:', err);
      if (err.response) {
        setPasswordError(err.response.data?.detail || 'Failed to update password.');
      } else {
        setPasswordError('Auth Microservice is unreachable.');
      }
    } finally {
      setIsUpdatingPassword(false);
    }
  };

  const isAuthenticated = !!auth.accessToken;

  return (
    <div className="dashboard-page">
      {/* Background Neon Glow Orbs */}
      <div className="glow-orb-1" />
      <div className="glow-orb-2" />

      <main className="w-full max-w-4xl px-6 py-12 z-10">

        {!isAuthenticated ? (
          /* ================= UNAUTHENTICATED STATE ================= */
          <div className="text-center max-w-xl mx-auto space-y-8 animate-fadeIn">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-xs font-medium text-zinc-400">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              Microservice Gateway Active
            </div>

            <div className="space-y-4">
              <h1 className="text-4xl md:text-5xl font-black tracking-tight text-white leading-tight">
                Backend Access <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-indigo-400">Restricted</span>
              </h1>
              <p className="text-base text-zinc-400 leading-relaxed">
                Authentication is fully decoupled. The API Gateway monitors resource limits and filters requests at the edge before hitting the downstream Django services.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
              <Link
                href="/login"
                className="btn-primary"
              >
                Sign in to Dashboard
              </Link>
              <a
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="btn-secondary"
              >
                Documentation
              </a>
            </div>
          </div>
        ) : (
          /* ================= AUTHENTICATED STATE ================= */
          <div className="space-y-8 animate-fadeIn">

            {/* Header Dashboard Navigation */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-6 border-b border-zinc-800/80">
              <div>
                <h1 className="text-3xl font-extrabold tracking-tight">System Control Center</h1>
                <p className="text-sm text-zinc-400">Authenticated via Centralized JWT Gateway</p>
              </div>
              <button
                onClick={logout}
                className="btn-secondary"
              >
                Sign Out
              </button>
            </div>

            {/* Profile Info Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
 
               {/* ID Card */}
               <div className="dashboard-card">
                 <span className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Identity payload</span>
                 <div className="text-2xl font-bold text-white truncate">{auth.user?.username}</div>
                 <div className="text-xs text-zinc-400 font-mono truncate">{auth.user?.email}</div>
               </div>
 
               {/* Role Card */}
               <div className="dashboard-card">
                 <span className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Assigned role</span>
                 <div className="flex items-center gap-2">
                   <span className="inline-flex items-center justify-center w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                   <div className="text-2xl font-bold text-emerald-400 uppercase">{auth.user?.role}</div>
                 </div>
                 <div className="text-xs text-zinc-400">Gateway Level Enforcement</div>
               </div>
 
               {/* Access Token Card */}
               <div className="dashboard-card">
                 <span className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Access token status</span>
                 <div className="text-lg font-mono text-zinc-400 truncate max-w-xs">{auth.accessToken}</div>
                 <div className="text-xs text-violet-400 font-medium">Silent rotation on expiry</div>
               </div>
             </div>

            {/* API Sandbox Section */}
            <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-2xl p-8 space-y-6">
              <div>
                <h3 className="text-lg font-bold text-white">API Gateway Sandbox</h3>
                <p className="text-xs text-zinc-400 mt-1">
                  Test the token injection system. Clicking the test button will trigger a secure HTTP request to your proxy gateway route.
                </p>
              </div>

              <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
                <button
                  onClick={handleTestSecureCall}
                  disabled={isCallingApi}
                  className="btn-primary"
                >
                  {isCallingApi ? 'Calling Gateway...' : 'Test Private Gateway Call'}
                </button>
                <span className="text-xs text-zinc-500">
                  Target Endpoint: <code className="font-mono bg-white border border-zinc-200 px-2 py-1 rounded text-zinc-400" style={{ backgroundColor: '#ffffff' }}>GET /api/v1/dashboard/</code>
                </span>
              </div>

              {/* API Output Window */}
              {(apiResponse || apiError) && (
                <div className="border border-zinc-800 rounded-xl overflow-hidden animate-fadeIn">
                  <div className="bg-zinc-900/80 px-4 py-2 border-b border-zinc-800 text-xs font-semibold text-zinc-400 flex items-center justify-between">
                    <span>Gateway Downstream Output</span>
                    <span className="font-mono text-violet-400">{apiResponse ? '200 OK' : 'ERROR'}</span>
                  </div>
                  <div className="bg-zinc-950 p-4 font-mono text-xs overflow-x-auto max-h-60">
                    {apiResponse && (
                      <pre className="text-emerald-400">{JSON.stringify(apiResponse, null, 2)}</pre>
                    )}
                    {apiError && (
                      <pre className="text-red-400">{apiError}</pre>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Account Settings Section */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              
              {/* Change Username Card */}
              <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-2xl p-8 space-y-6">
                <div>
                  <h3 className="text-lg font-bold text-white">Change Username</h3>
                  <p className="text-xs text-zinc-400 mt-1">
                    Update your system login name.
                  </p>
                </div>

                <form onSubmit={handleUpdateUsername} className="space-y-4">
                  {usernameError && (
                    <div className="p-3 rounded-lg bg-red-950/40 border border-red-800/50 text-red-300 text-xs animate-fadeIn">
                      {usernameError}
                    </div>
                  )}
                  {usernameSuccess && (
                    <div className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-800/50 text-emerald-300 text-xs animate-fadeIn">
                      {usernameSuccess}
                    </div>
                  )}

                  <div className="space-y-2">
                    <label htmlFor="new-username" className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                      New Username
                    </label>
                    <input
                      id="new-username"
                      type="text"
                      required
                      placeholder="new_username"
                      value={newUsername}
                      onChange={(e) => setNewUsername(e.target.value)}
                      className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-violet-500 focus:border-violet-500 transition-all duration-200"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={isUpdatingUsername}
                    className="btn-primary w-full"
                  >
                    {isUpdatingUsername ? 'Updating...' : 'Update Username'}
                  </button>
                </form>
              </div>

              {/* Change Password Card */}
              <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-2xl p-8 space-y-6">
                <div>
                  <h3 className="text-lg font-bold text-white">Change Password</h3>
                  <p className="text-xs text-zinc-400 mt-1">
                    Change your password credentials securely.
                  </p>
                </div>

                <form onSubmit={handleUpdatePassword} className="space-y-4">
                  {passwordError && (
                    <div className="p-3 rounded-lg bg-red-950/40 border border-red-800/50 text-red-300 text-xs animate-fadeIn">
                      {passwordError}
                    </div>
                  )}
                  {passwordSuccess && (
                    <div className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-800/50 text-emerald-300 text-xs animate-fadeIn">
                      {passwordSuccess}
                    </div>
                  )}

                  <div className="space-y-2">
                    <label htmlFor="old-password" className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                      Current Password
                    </label>
                    <input
                      id="old-password"
                      type="password"
                      required
                      placeholder="••••••••"
                      value={oldPassword}
                      onChange={(e) => setOldPassword(e.target.value)}
                      className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-violet-500 focus:border-violet-500 transition-all duration-200"
                    />
                  </div>

                  <div className="space-y-2">
                    <label htmlFor="new-password" className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                      New Password
                    </label>
                    <input
                      id="new-password"
                      type="password"
                      required
                      placeholder="••••••••"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-violet-500 focus:border-violet-500 transition-all duration-200"
                    />
                  </div>

                  <div className="space-y-2">
                    <label htmlFor="confirm-password" className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                      Confirm New Password
                    </label>
                    <input
                      id="confirm-password"
                      type="password"
                      required
                      placeholder="••••••••"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-violet-500 focus:border-violet-500 transition-all duration-200"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={isUpdatingPassword}
                    className="btn-primary w-full"
                  >
                    {isUpdatingPassword ? 'Updating...' : 'Update Password'}
                  </button>
                </form>
              </div>

            </div>

          </div>
        )}
      </main>
    </div>
  );
}
