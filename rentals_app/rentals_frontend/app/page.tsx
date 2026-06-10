// c:\Users\ritam\wtvision\rentals_app\rentals_frontend\app\page.tsx
'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useAuth } from './context/AuthContext';
import { useAxiosPrivate } from '@/app/hooks';

interface Category {
  id: string;
  name: string;
  icon: string | null;
  schema: any[];
}

interface Item {
  id: string;
  title: string;
  description: string;
  categoryId: string;
  locationName: string;
  latitude: number;
  longitude: number;
  pricePerDay: string;
  isDigital: boolean;
  category: {
    name: string;
    icon: string | null;
  };
  attributes: Record<string, any>;
  distance?: number;
}

interface Booking {
  id: string;
  itemId: string;
  renterUsername: string;
  startDate: string;
  endDate: string;
  status: string;
  accessToken: string;
  item: Item;
}

export default function Home() {
  const { auth, logout } = useAuth();
  const axiosPrivate = useAxiosPrivate();

  // Categories & Items list
  const [categories, setCategories] = useState<Category[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [loadingItems, setLoadingItems] = useState(false);

  // Search & Filters state
  const [selectedCategoryId, setSelectedCategoryId] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [enableProximity, setEnableProximity] = useState(false);
  const [userLat, setUserLat] = useState('40.7128'); // default New York lat
  const [userLon, setUserLon] = useState('-74.0060'); // default New York lon
  const [maxDistance, setMaxDistance] = useState('50');

  // Bookings list state
  const [bookingsTab, setBookingsTab] = useState<'rentals' | 'listings'>('rentals');
  const [myRentals, setMyRentals] = useState<Booking[]>([]);
  const [myListings, setMyListings] = useState<Booking[]>([]);

  // Selected Booking Credentials Decrypted
  const [decryptedCreds, setDecryptedCreds] = useState<any>(null);
  const [decryptedCredsError, setDecryptedCredsError] = useState('');
  const [activeCredsBookingId, setActiveCredsBookingId] = useState<string | null>(null);

  // Form states for listing item
  const [listTitle, setListTitle] = useState('');
  const [listDescription, setListDescription] = useState('');
  const [listCategoryId, setListCategoryId] = useState('');
  const [listPrice, setListPrice] = useState('');
  const [listLocation, setListLocation] = useState('');
  const [listLat, setListLat] = useState('');
  const [listLon, setListLon] = useState('');
  const [listIsDigital, setListIsDigital] = useState(false);
  const [listCredData, setListCredData] = useState('');
  const [listAccessInstructions, setListAccessInstructions] = useState('');
  const [dynamicAttributes, setDynamicAttributes] = useState<Record<string, any>>({});

  const [listSuccess, setListSuccess] = useState('');
  const [listError, setListError] = useState('');
  const [isListing, setIsListing] = useState(false);

  // Booking action states
  const [activeBookingItemId, setActiveBookingItemId] = useState<string | null>(null);
  const [bookingStartDate, setBookingStartDate] = useState('');
  const [bookingEndDate, setBookingEndDate] = useState('');
  const [bookingSuccess, setBookingSuccess] = useState('');
  const [bookingError, setBookingError] = useState('');
  const [isBooking, setIsBooking] = useState(false);

  const isAuthenticated = !!auth.accessToken;

  // Load initial data
  useEffect(() => {
    fetchCategories();
    fetchCatalog();
    if (isAuthenticated) {
      fetchRentals();
      fetchListings();
    }
  }, [isAuthenticated]);

  // Refetch catalog on filter changes
  useEffect(() => {
    fetchCatalog();
  }, [selectedCategoryId, searchQuery, enableProximity]);

  const fetchCategories = async () => {
    try {
      const response = await axiosPrivate.get('/api/v1/rentals/categories');
      setCategories(response.data);
    } catch (err) {
      console.error('Error fetching categories:', err);
    }
  };

  const fetchCatalog = async () => {
    setLoadingItems(true);
    try {
      const params: any = {};
      if (selectedCategoryId) params.categoryId = selectedCategoryId;
      if (searchQuery) params.search = searchQuery;

      if (enableProximity) {
        const lat = parseFloat(userLat);
        const lon = parseFloat(userLon);
        const dist = parseFloat(maxDistance);
        if (!isNaN(lat) && !isNaN(lon)) {
          params.latitude = lat;
          params.longitude = lon;
          if (!isNaN(dist)) params.maxDistance = dist;
        }
      }

      const response = await axiosPrivate.get('/api/v1/rentals/items', { params });
      setItems(response.data);
    } catch (err) {
      console.error('Error fetching catalog:', err);
    } finally {
      setLoadingItems(false);
    }
  };

  const fetchRentals = async () => {
    try {
      const response = await axiosPrivate.get('/api/v1/rentals/bookings/my-rentals');
      setMyRentals(response.data);
    } catch (err) {
      console.error('Error fetching rentals:', err);
    }
  };

  const fetchListings = async () => {
    try {
      const response = await axiosPrivate.get('/api/v1/rentals/bookings/my-listings');
      setMyListings(response.data);
    } catch (err) {
      console.error('Error fetching listings bookings:', err);
    }
  };

  // Fetch coordinates using geolocation
  const handleUseCurrentLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setUserLat(position.coords.latitude.toFixed(6));
          setUserLon(position.coords.longitude.toFixed(6));
          // Trigger fetchCatalog with updated values
          setTimeout(fetchCatalog, 100);
        },
        (err) => {
          alert('Could not retrieve geolocation data. Verify browser permissions.');
        }
      );
    } else {
      alert('Geolocation is not supported by your browser.');
    }
  };

  // Listing item category selection handler
  const handleCategorySelectChange = (catId: string) => {
    setListCategoryId(catId);
    setDynamicAttributes({}); // Reset dynamic attributes
  };

  const selectedCategorySchema = categories.find((c) => c.id === listCategoryId)?.schema || [];

  const handleDynamicAttrChange = (fieldName: string, val: any) => {
    setDynamicAttributes((prev) => ({
      ...prev,
      [fieldName]: val,
    }));
  };

  const handleListItem = async (e: React.SubmitEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsListing(true);
    setListSuccess('');
    setListError('');

    if (!listTitle || !listDescription || !listCategoryId || !listLocation || !listPrice) {
      setListError('Please fill out all required parameters.');
      setIsListing(false);
      return;
    }

    try {
      const payload: any = {
        title: listTitle,
        description: listDescription,
        categoryId: listCategoryId,
        attributes: dynamicAttributes,
        locationName: listLocation,
        latitude: parseFloat(listLat) || 0.0,
        longitude: parseFloat(listLon) || 0.0,
        pricePerDay: parseFloat(listPrice),
        isDigital: listIsDigital,
      };

      if (listIsDigital) {
        payload.credentialData = listCredData;
        payload.accessInstructions = listAccessInstructions;
      }

      await axiosPrivate.post('/api/v1/rentals/items', payload);
      setListSuccess('Your item listing has been posted successfully!');

      // Reset form
      setListTitle('');
      setListDescription('');
      setListCategoryId('');
      setListPrice('');
      setListLocation('');
      setListLat('');
      setListLon('');
      setListIsDigital(false);
      setListCredData('');
      setListAccessInstructions('');
      setDynamicAttributes({});

      // Refetch catalog & listings
      fetchCatalog();
      fetchListings();
    } catch (err: any) {
      console.error('List item error:', err);
      setListError(err.response?.data?.message || 'Error occurred while creating listing.');
    } finally {
      setIsListing(false);
    }
  };

  const handleBookItem = async (e: React.SubmitEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsBooking(true);
    setBookingSuccess('');
    setBookingError('');

    if (!bookingStartDate || !bookingEndDate || !activeBookingItemId) {
      setBookingError('Please select both start and end dates.');
      setIsBooking(false);
      return;
    }

    try {
      await axiosPrivate.post('/api/v1/rentals/bookings', {
        itemId: activeBookingItemId,
        startDate: bookingStartDate,
        endDate: bookingEndDate,
      });

      setBookingSuccess('Booking completed successfully! Token issued.');
      setBookingStartDate('');
      setBookingEndDate('');
      setActiveBookingItemId(null);

      // Refetch rentals
      fetchRentals();
    } catch (err: any) {
      console.error('Booking error:', err);
      setBookingError(err.response?.data?.message || 'Failed to book item.');
    } finally {
      setIsBooking(false);
    }
  };

  const decryptCredentials = async (booking: Booking) => {
    setDecryptedCreds(null);
    setDecryptedCredsError('');
    setActiveCredsBookingId(booking.id);

    try {
      const response = await axiosPrivate.get(`/api/v1/rentals/bookings/${booking.id}/credential`, {
        params: { access_token: booking.accessToken },
      });
      setDecryptedCreds(response.data);
    } catch (err: any) {
      console.error('Credentials decryption error:', err);
      setDecryptedCredsError(err.response?.data?.message || 'Failed to retrieve secure credentials.');
    }
  };

  const getEmojiIcon = (iconName: string | null) => {
    if (!iconName) return '📦';
    switch (iconName.toLowerCase()) {
      case 'hammer': return '🛠️';
      case 'key': return '🔑';
      case 'tent': return '⛺';
      default: return '📦';
    }
  };

  return (
    <div className="dashboard-page">
      {/* Background Neon Glow Orbs */}
      <div className="glow-orb-1" />
      <div className="glow-orb-2" />

      <main className="w-full max-w-6xl px-6 py-12 z-10 space-y-12">
        {/* Header Block */}
        <div className="white-block flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight">Rental Hub</h1>
            <p className="text-sm text-zinc-400">Artsy Uniform Rentals & Digital Credentials Provider</p>
          </div>
          {isAuthenticated ? (
            <div className="flex items-center gap-4">
              <span className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
                Hi, {auth.user?.username || auth.user?.email.split('@')[0]}
              </span>
              <button onClick={logout} className="btn-secondary">
                Sign Out
              </button>
            </div>
          ) : (
            <Link href="/login" className="btn-primary">
              Sign In to Access Portal
            </Link>
          )}
        </div>

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

          {/* Left Column: Filter & Search controls */}
          <div className="lg:col-span-1 space-y-6">

            {/* Catalog Filter Box */}
            <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-2xl p-6 space-y-6">
              <h3 className="text-lg font-bold text-white">Filter Catalog</h3>

              {/* Text Search */}
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Search</label>
                <input
                  type="text"
                  placeholder="Search title, details, location..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-violet-500 focus:border-violet-500"
                />
              </div>

              {/* Categories */}
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Category</label>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => setSelectedCategoryId('')}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-200 ${selectedCategoryId === ''
                      ? 'bg-amber-100 text-amber-900 border-amber-500'
                      : 'bg-zinc-900/40 text-zinc-400 border-zinc-800 hover:border-zinc-700'
                      }`}
                  >
                    All Categories
                  </button>
                  {categories.map((cat) => (
                    <button
                      key={cat.id}
                      onClick={() => setSelectedCategoryId(cat.id)}
                      className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-200 flex items-center gap-1.5 ${selectedCategoryId === cat.id
                        ? 'bg-amber-100 text-amber-900 border-amber-500'
                        : 'bg-zinc-900/40 text-zinc-400 border-zinc-800 hover:border-zinc-700'
                        }`}
                    >
                      <span>{getEmojiIcon(cat.icon)}</span>
                      <span>{cat.name}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Proximity Location Sorting */}
              <div className="space-y-4 pt-2 border-t border-zinc-800/40">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold text-white">Proximity Sorting</span>
                  <input
                    type="checkbox"
                    checked={enableProximity}
                    onChange={(e) => setEnableProximity(e.target.checked)}
                    className="w-4 h-4 rounded text-amber-600 focus:ring-amber-500 accent-amber-600"
                  />
                </div>

                {enableProximity && (
                  <div className="space-y-3 animate-fadeIn">
                    <div className="grid grid-cols-2 gap-2">
                      <div className="space-y-1">
                        <label className="text-[10px] font-semibold uppercase text-zinc-400">Lat</label>
                        <input
                          type="number"
                          step="0.0001"
                          value={userLat}
                          onChange={(e) => setUserLat(e.target.value)}
                          className="w-full bg-zinc-950/85 border border-zinc-800 rounded-lg p-2 text-xs text-white"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] font-semibold uppercase text-zinc-400">Lon</label>
                        <input
                          type="number"
                          step="0.0001"
                          value={userLon}
                          onChange={(e) => setUserLon(e.target.value)}
                          className="w-full bg-zinc-950/85 border border-zinc-800 rounded-lg p-2 text-xs text-white"
                        />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] font-semibold uppercase text-zinc-400">Max Distance (km)</label>
                      <input
                        type="number"
                        value={maxDistance}
                        onChange={(e) => setMaxDistance(e.target.value)}
                        className="w-full bg-zinc-950/85 border border-zinc-800 rounded-lg p-2 text-xs text-white"
                      />
                    </div>

                    <button
                      type="button"
                      onClick={handleUseCurrentLocation}
                      className="w-full btn-secondary text-xs py-2"
                    >
                      📍 Use Geolocation Location
                    </button>
                  </div>
                )}
              </div>

            </div>

            {/* List Item Box (Authenticated only) */}
            {isAuthenticated ? (
              <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-2xl p-6 space-y-6">
                <div>
                  <h3 className="text-lg font-bold text-white">List Item for Rent</h3>
                  <p className="text-xs text-zinc-400 mt-1">Rent tools, camping equipment or SaaS credentials.</p>
                </div>

                <form onSubmit={handleListItem} className="space-y-4">
                  {listError && (
                    <div className="p-3 rounded-lg bg-red-950/40 border border-red-800/50 text-red-300 text-xs">
                      {listError}
                    </div>
                  )}
                  {listSuccess && (
                    <div className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-800/50 text-emerald-300 text-xs">
                      {listSuccess}
                    </div>
                  )}

                  <div className="space-y-1">
                    <label className="text-[10px] font-semibold uppercase text-zinc-400">Title</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Cordless Drill 20V"
                      value={listTitle}
                      onChange={(e) => setListTitle(e.target.value)}
                      className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[10px] font-semibold uppercase text-zinc-400">Description</label>
                    <textarea
                      required
                      placeholder="Describe the condition, usage guidelines..."
                      value={listDescription}
                      onChange={(e) => setListDescription(e.target.value)}
                      className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white min-h-[60px]"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <label className="text-[10px] font-semibold uppercase text-zinc-400">Price Per Day ($)</label>
                      <input
                        type="number"
                        step="0.01"
                        required
                        placeholder="15.00"
                        value={listPrice}
                        onChange={(e) => setListPrice(e.target.value)}
                        className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] font-semibold uppercase text-zinc-400">Category</label>
                      <select
                        required
                        value={listCategoryId}
                        onChange={(e) => handleCategorySelectChange(e.target.value)}
                        className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none"
                      >
                        <option value="">Select Category</option>
                        {categories.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* Dynamic Category Attributes */}
                  {selectedCategorySchema.length > 0 && (
                    <div className="p-3 bg-zinc-950/60 border border-zinc-800/80 rounded-xl space-y-3">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-amber-500">Category Attributes</span>
                      {selectedCategorySchema.map((field: any) => (
                        <div key={field.field_name} className="space-y-1">
                          <label className="text-[9px] font-semibold uppercase text-zinc-400">
                            {field.field_name.replace('_', ' ')} {field.required ? '*' : ''}
                          </label>
                          <input
                            type={field.type === 'number' ? 'number' : 'text'}
                            required={field.required}
                            placeholder={`Enter ${field.field_name.replace('_', ' ')}`}
                            value={dynamicAttributes[field.field_name] || ''}
                            onChange={(e) => handleDynamicAttrChange(field.field_name, e.target.value)}
                            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-2 py-1 text-xs text-white"
                          />
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="space-y-1">
                    <label className="text-[10px] font-semibold uppercase text-zinc-400">Location Name</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Brooklyn, NY"
                      value={listLocation}
                      onChange={(e) => setListLocation(e.target.value)}
                      className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <label className="text-[10px] font-semibold uppercase text-zinc-400">Location Lat</label>
                      <input
                        type="number"
                        step="0.000001"
                        placeholder="40.7128"
                        value={listLat}
                        onChange={(e) => setListLat(e.target.value)}
                        className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[10px] font-semibold uppercase text-zinc-400">Location Lon</label>
                      <input
                        type="number"
                        step="0.000001"
                        placeholder="-74.0060"
                        value={listLon}
                        onChange={(e) => setListLon(e.target.value)}
                        className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white"
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between py-1 border-t border-zinc-800/40">
                    <span className="text-xs text-white font-semibold">Is Digital Credentials?</span>
                    <input
                      type="checkbox"
                      checked={listIsDigital}
                      onChange={(e) => setListIsDigital(e.target.checked)}
                      className="w-4 h-4 rounded text-amber-600 focus:ring-amber-500 accent-amber-600"
                    />
                  </div>

                  {listIsDigital && (
                    <div className="p-3 bg-zinc-950/80 border border-zinc-800/80 rounded-xl space-y-3 animate-fadeIn">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-violet-400">Secure Digital Credentials</span>
                      <div className="space-y-1">
                        <label className="text-[9px] font-semibold uppercase text-zinc-400">Credential Data (JSON or Raw Text)</label>
                        <textarea
                          required
                          placeholder='e.g. {"username":"admin","token":"xyz"}'
                          value={listCredData}
                          onChange={(e) => setListCredData(e.target.value)}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-2 py-1 text-xs text-white font-mono min-h-[50px]"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[9px] font-semibold uppercase text-zinc-400">Access Instructions</label>
                        <input
                          type="text"
                          required
                          placeholder="e.g. Go to platform.com/login and use credentials."
                          value={listAccessInstructions}
                          onChange={(e) => setListAccessInstructions(e.target.value)}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-2 py-1 text-xs text-white"
                        />
                      </div>
                    </div>
                  )}

                  <button type="submit" disabled={isListing} className="btn-primary w-full text-xs py-2">
                    {isListing ? 'Posting Listing...' : 'Submit Listing'}
                  </button>
                </form>
              </div>
            ) : (
              <div className="bg-zinc-900/20 border border-zinc-800/50 rounded-2xl p-6 text-center space-y-4">
                <span className="text-3xl">🔑</span>
                <h3 className="text-sm font-bold text-white">Listing Items</h3>
                <p className="text-xs text-zinc-400">Sign in to list items for rent and manage bookings.</p>
                <Link href="/login" className="btn-secondary w-full inline-block text-xs py-2">
                  Sign In
                </Link>
              </div>
            )}
          </div>

          {/* Right Column: Catalog Grid & Booking Forms (takes 2 columns) */}
          <div className="lg:col-span-2 space-y-8">

            {/* Catalog list */}
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h2 className="text-xl font-bold text-white">Available Rentals</h2>
                <span className="text-xs bg-zinc-900/60 border border-zinc-800 px-2.5 py-1 rounded-full text-zinc-400 font-mono">
                  {items.length} item{items.length !== 1 ? 's' : ''} found
                </span>
              </div>

              {loadingItems ? (
                <div className="p-12 text-center text-zinc-500">Loading catalog items...</div>
              ) : items.length === 0 ? (
                <div className="p-12 border-2 border-dashed border-zinc-800 rounded-2xl text-center text-zinc-500">
                  No rental items match the current search filters.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {items.map((item) => (
                    <div key={item.id} className="dashboard-card flex flex-col justify-between">
                      <div className="space-y-3">
                        {/* Title & Badge */}
                        <div className="flex justify-between items-start gap-4">
                          <div>
                            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-zinc-950 border border-zinc-800 text-[10px] font-mono text-amber-500">
                              {getEmojiIcon(item.category.icon)} {item.category.name}
                            </span>
                            <h3 className="text-lg font-bold text-white mt-1.5">{item.title}</h3>
                          </div>
                          <div className="text-right">
                            <div className="text-lg font-bold text-emerald-400">${parseFloat(item.pricePerDay).toFixed(2)}</div>
                            <span className="text-[10px] text-zinc-400 font-mono">per day</span>
                          </div>
                        </div>

                        {/* Description */}
                        <p className="text-xs text-zinc-300 line-clamp-3">{item.description}</p>

                        {/* Attributes rendering */}
                        {Object.keys(item.attributes).length > 0 && (
                          <div className="flex flex-wrap gap-2 py-1 border-t border-b border-zinc-800/40">
                            {Object.entries(item.attributes).map(([key, val]) => (
                              <span key={key} className="text-[10px] bg-zinc-950/60 border border-zinc-800/60 px-2 py-0.5 rounded text-zinc-300 font-mono">
                                <span className="text-zinc-500">{key.replace('_', ' ')}:</span> {val}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Location / Proximity */}
                        <div className="flex justify-between items-center text-xs text-zinc-400">
                          <span>📍 {item.locationName}</span>
                          {item.distance !== undefined && (
                            <span className="text-amber-500 font-bold">{item.distance} km away</span>
                          )}
                        </div>
                      </div>

                      {/* Booking / Details Trigger */}
                      <div className="mt-4 pt-3 border-t border-zinc-800/30 flex justify-between items-center">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${item.isDigital
                          ? 'bg-violet-950/40 border border-violet-800/50 text-violet-300'
                          : 'bg-zinc-950 border border-zinc-800 text-zinc-400'
                          }`}>
                          {item.isDigital ? '💾 Digital Credentials' : '📦 Physical Rental'}
                        </span>

                        {isAuthenticated ? (
                          activeBookingItemId === item.id ? (
                            <form onSubmit={handleBookItem} className="w-full space-y-2 mt-2 animate-fadeIn">
                              {bookingError && (
                                <div className="p-2 bg-red-950/40 border border-red-800/50 text-red-300 text-[10px] rounded">
                                  {bookingError}
                                </div>
                              )}
                              <div className="grid grid-cols-2 gap-2 text-[10px]">
                                <div>
                                  <label className="text-zinc-500 font-bold uppercase">Start Date</label>
                                  <input
                                    type="date"
                                    required
                                    value={bookingStartDate}
                                    onChange={(e) => setBookingStartDate(e.target.value)}
                                    className="w-full bg-zinc-950 border border-zinc-800 rounded p-1 text-white"
                                  />
                                </div>
                                <div>
                                  <label className="text-zinc-500 font-bold uppercase">End Date</label>
                                  <input
                                    type="date"
                                    required
                                    value={bookingEndDate}
                                    onChange={(e) => setBookingEndDate(e.target.value)}
                                    className="w-full bg-zinc-950 border border-zinc-800 rounded p-1 text-white"
                                  />
                                </div>
                              </div>
                              <div className="flex gap-2">
                                <button type="submit" disabled={isBooking} className="w-full btn-primary text-[10px] py-1.5">
                                  {isBooking ? 'Booking...' : 'Confirm Book'}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setActiveBookingItemId(null)}
                                  className="w-1/2 btn-secondary text-[10px] py-1.5"
                                >
                                  Cancel
                                </button>
                              </div>
                            </form>
                          ) : (
                            <button
                              onClick={() => {
                                setBookingSuccess('');
                                setBookingError('');
                                setActiveBookingItemId(item.id);
                              }}
                              className="btn-primary text-xs py-1 px-3"
                            >
                              Book Now
                            </button>
                          )
                        ) : (
                          <span className="text-[10px] text-zinc-500">Sign in to book</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Bookings & Credentials management (Authenticated only) */}
            {isAuthenticated && (
              <div className="space-y-4">
                <div className="border-b border-zinc-800 flex justify-between items-center">
                  <div className="flex gap-4">
                    <button
                      onClick={() => setBookingsTab('rentals')}
                      className={`pb-2 text-sm font-bold border-b-2 transition-all duration-200 ${bookingsTab === 'rentals' ? 'border-amber-500 text-white' : 'border-transparent text-zinc-500 hover:text-zinc-300'
                        }`}
                    >
                      My Rentals ({myRentals.length})
                    </button>
                    <button
                      onClick={() => setBookingsTab('listings')}
                      className={`pb-2 text-sm font-bold border-b-2 transition-all duration-200 ${bookingsTab === 'listings' ? 'border-amber-500 text-white' : 'border-transparent text-zinc-500 hover:text-zinc-300'
                        }`}
                    >
                      My Listings Orders ({myListings.length})
                    </button>
                  </div>
                </div>

                {/* Tab Content */}
                {bookingsTab === 'rentals' ? (
                  <div className="space-y-4">
                    {myRentals.length === 0 ? (
                      <p className="text-xs text-zinc-500">You have no active or pending rental bookings.</p>
                    ) : (
                      myRentals.map((booking) => (
                        <div key={booking.id} className="white-block py-4 px-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                          <div>
                            <div className="flex items-center gap-2">
                              <h4 className="font-bold text-white">{booking.item.title}</h4>
                              <span className={`text-[9px] px-2 py-0.5 rounded font-mono ${booking.status === 'active'
                                ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-800/40'
                                : 'bg-zinc-950 text-zinc-400 border border-zinc-800'
                                }`}>
                                {booking.status}
                              </span>
                            </div>
                            <div className="text-xs text-zinc-400 mt-1 font-mono">
                              Period: {new Date(booking.startDate).toLocaleDateString()} - {new Date(booking.endDate).toLocaleDateString()}
                            </div>
                            {booking.item.isDigital && (
                              <div className="text-[10px] text-violet-400 font-mono mt-1">
                                Token: {booking.accessToken}
                              </div>
                            )}
                          </div>

                          <div className="flex gap-2">
                            {booking.item.isDigital && booking.status === 'active' && (
                              <button
                                onClick={() => decryptCredentials(booking)}
                                className="btn-primary text-xs py-1.5 px-3"
                              >
                                Decrypt Credentials
                              </button>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                ) : (
                  <div className="space-y-4">
                    {myListings.length === 0 ? (
                      <p className="text-xs text-zinc-500">No renter has booked any of your listings yet.</p>
                    ) : (
                      myListings.map((booking) => (
                        <div key={booking.id} className="white-block py-4 px-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                          <div>
                            <div className="flex items-center gap-2">
                              <h4 className="font-bold text-white">{booking.item.title}</h4>
                              <span className="text-[9px] px-2 py-0.5 rounded bg-zinc-950 text-zinc-400 border border-zinc-800 font-mono">
                                Renter: {booking.renterUsername}
                              </span>
                            </div>
                            <div className="text-xs text-zinc-400 mt-1 font-mono">
                              Period: {new Date(booking.startDate).toLocaleDateString()} - {new Date(booking.endDate).toLocaleDateString()}
                            </div>
                          </div>
                          <span className={`text-[10px] font-mono uppercase font-bold text-right ${booking.status === 'active' ? 'text-emerald-400' : 'text-zinc-500'
                            }`}>
                            {booking.status}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                )}

                {/* Digital Credentials View Output (shows decrypt outputs) */}
                {activeCredsBookingId && (
                  <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 space-y-4 animate-fadeIn">
                    <div className="flex justify-between items-center border-b border-zinc-800 pb-2">
                      <span className="text-xs font-bold text-white flex items-center gap-1.5">
                        🔐 Secure Decrypted Payload
                      </span>
                      <button onClick={() => setActiveCredsBookingId(null)} className="text-xs text-zinc-500 hover:text-zinc-400">
                        Dismiss
                      </button>
                    </div>

                    {decryptedCredsError && (
                      <pre className="text-red-400 text-xs font-mono">{decryptedCredsError}</pre>
                    )}

                    {decryptedCreds && (
                      <div className="space-y-4 font-mono text-xs">
                        <div className="bg-zinc-900/60 p-4 rounded-xl border border-zinc-800 text-emerald-400 overflow-x-auto">
                          <pre>{JSON.stringify(decryptedCreds.credentials, null, 2)}</pre>
                        </div>
                        <div className="space-y-1 bg-zinc-900/30 p-4 rounded-xl border border-zinc-800/40">
                          <span className="text-[10px] font-bold text-zinc-500 uppercase">Usage Instructions</span>
                          <p className="text-zinc-300">{decryptedCreds.accessInstructions}</p>
                        </div>
                        <div className="text-[10px] text-zinc-500 text-right">
                          Lease Remaining: <span className="text-amber-500 font-bold">{decryptedCreds.tenureRemainingSeconds}s</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}

              </div>
            )}

          </div>

        </div>

      </main>
    </div>
  );
}
