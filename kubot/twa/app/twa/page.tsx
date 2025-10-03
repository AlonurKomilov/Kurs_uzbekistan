'use client';

import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import '../../i18n';

// Types
interface BankRate {
  bank_id: number;
  bank_name: string;
  bank_slug: string;
  code: string;
  buy: string;
  sell: string;
  fetched_at: string;
}

interface KPIData {
  minSell: number;
  avgSell: number;
  maxSell: number;
  count: number;
}

interface TelegramWebApp {
  initData?: string;
  initDataUnsafe?: {
    user?: {
      id: number;
      first_name: string;
      language_code?: string;
    };
  };
  ready?: () => void;
  expand?: () => void;
  MainButton?: {
    show: () => void;
    hide: () => void;
  };
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}

const CURRENCIES = ['USD', 'EUR', 'RUB'] as const;
type Currency = typeof CURRENCIES[number];

const LANGUAGES = [
  { code: 'uz_cy', flag: '🇺🇿', name: 'UZ' },
  { code: 'ru', flag: '🇷🇺', name: 'RU' },
  { code: 'en', flag: '🇺🇸', name: 'EN' },
] as const;

export default function TWAPage() {
  const { t, i18n } = useTranslation();
  
  // State
  const [selectedCurrency, setSelectedCurrency] = useState<Currency>('USD');
  const [bankRates, setBankRates] = useState<BankRate[]>([]);
  const [kpiData, setKpiData] = useState<KPIData | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [authHeaders, setAuthHeaders] = useState<Record<string, string>>({});

  // Initialize Telegram WebApp and authentication
  useEffect(() => {
    const initTelegramWebApp = async () => {
      // Check if we're in Telegram WebApp
      const tg = window.Telegram?.WebApp;
      
      if (tg && tg.initData) {
        // Production: Use Telegram WebApp data
        tg.ready?.();
        tg.expand?.();
        
        const headers = {
          'X-Telegram-WebApp-Data': tg.initData
        };
        
        setAuthHeaders(headers);
        
        try {
          // Get user's language from API
          const response = await fetch('/api/me', { headers });
          if (response.ok) {
            const userData = await response.json();
            await i18n.changeLanguage(userData.lang);
          }
        } catch (err) {
          console.warn('Failed to get user data:', err);
        }
      } else {
        // Development fallback: Check URL params or use default
        const urlParams = new URLSearchParams(window.location.search);
        const langParam = urlParams.get('lang');
        
        if (langParam && ['uz_cy', 'ru', 'en'].includes(langParam)) {
          await i18n.changeLanguage(langParam);
        }
        
        console.log('Development mode: No Telegram WebApp data');
      }
    };

    initTelegramWebApp();
  }, [i18n]);

  // Fetch bank rates
  const fetchBankRates = async (currency: Currency, showLoading = true) => {
    try {
      if (showLoading) {
        setLoading(true);
      } else {
        setUpdating(true);
      }
      
      setError(null);
      
      const response = await fetch(`/api/bank_rates?code=${currency}&limit=50&order=sell_desc`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data: BankRate[] = await response.json();
      setBankRates(data);
      
      // Calculate KPI data
      if (data.length > 0) {
        const sellRates = data.map(rate => parseFloat(rate.sell)).filter(rate => !isNaN(rate));
        
        const kpi: KPIData = {
          minSell: Math.min(...sellRates),
          avgSell: sellRates.reduce((sum, rate) => sum + rate, 0) / sellRates.length,
          maxSell: Math.max(...sellRates),
          count: data.length
        };
        
        setKpiData(kpi);
      } else {
        setKpiData(null);
      }
    } catch (err) {
      console.error('Failed to fetch bank rates:', err);
      setError(t('error_loading'));
    } finally {
      setLoading(false);
      setUpdating(false);
    }
  };

  // Language change handler
  const handleLanguageChange = async (langCode: string) => {
    try {
      // If we have auth headers, update user's language preference
      if (Object.keys(authHeaders).length > 0) {
        await fetch('/api/me/lang', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...authHeaders
          },
          body: JSON.stringify({ lang: langCode })
        });
      }
      
      // Change i18n language
      await i18n.changeLanguage(langCode);
      
      // Store in localStorage for persistence
      localStorage.setItem('i18nextLng', langCode);
    } catch (err) {
      console.error('Failed to change language:', err);
    }
  };

  // Format relative time
  const formatRelativeTime = (dateString: string): string => {
    const now = new Date();
    const date = new Date(dateString);
    const diffMs = now.getTime() - date.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    
    if (diffMinutes < 1) return t('just_now');
    if (diffMinutes < 60) return `${diffMinutes} ${t('minutes')} ${t('ago')}`;
    
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours} ${t('hours')} ${t('ago')}`;
    
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} ${t('days')} ${t('ago')}`;
  };

  // Format number for display
  const formatNumber = (num: number, decimals = 0): string => {
    return num.toLocaleString('en-US', { 
      minimumFractionDigits: decimals, 
      maximumFractionDigits: decimals 
    });
  };

  // Initial load and currency change effect
  useEffect(() => {
    fetchBankRates(selectedCurrency);
  }, [selectedCurrency]);

  // Polling effect
  useEffect(() => {
    const interval = setInterval(() => {
      fetchBankRates(selectedCurrency, false);
    }, 60000); // 60 seconds

    return () => clearInterval(interval);
  }, [selectedCurrency]);

  const displayedRates = showAll ? bankRates : bankRates.slice(0, 10);

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="px-4 py-3">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold text-gray-900">
              {t('live_title')}
              {updating && (
                <span className="ml-2 text-sm text-blue-600 font-normal">
                  {t('updating')}
                </span>
              )}
            </h1>
            
            {/* Language Switch */}
            <div className="flex bg-gray-100 rounded-lg p-1">
              {LANGUAGES.map((lang) => (
                <button
                  key={lang.code}
                  onClick={() => handleLanguageChange(lang.code)}
                  className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all min-w-[44px] min-h-[44px] flex items-center justify-center ${
                    i18n.language === lang.code
                      ? 'bg-white text-blue-600 shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  {lang.name}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Currency Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="px-4">
          <div className="flex space-x-1">
            {CURRENCIES.map((currency) => (
              <button
                key={currency}
                onClick={() => setSelectedCurrency(currency)}
                className={`px-4 py-3 text-base font-medium border-b-2 transition-colors min-w-[44px] min-h-[44px] ${
                  selectedCurrency === currency
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {currency}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="p-4">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            <span className="ml-3 text-lg">{t('loading')}</span>
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-red-600 text-lg mb-4">{error}</p>
            <button
              onClick={() => fetchBankRates(selectedCurrency)}
              className="px-6 py-3 bg-blue-500 text-white rounded-lg text-base font-medium hover:bg-blue-600 transition-colors min-h-[44px]"
            >
              {t('retry')}
            </button>
          </div>
        ) : (
          <>
            {/* KPI Cards */}
            {kpiData && (
              <div className="grid grid-cols-2 gap-3 mb-6">
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="text-sm text-gray-600 mb-1">{t('min_sell')}</div>
                  <div className="text-xl font-bold text-green-600">
                    {formatNumber(kpiData.minSell)}
                  </div>
                </div>
                
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="text-sm text-gray-600 mb-1">{t('max_sell')}</div>
                  <div className="text-xl font-bold text-red-600">
                    {formatNumber(kpiData.maxSell)}
                  </div>
                </div>
                
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="text-sm text-gray-600 mb-1">{t('avg_sell')}</div>
                  <div className="text-xl font-bold text-blue-600">
                    {formatNumber(kpiData.avgSell)}
                  </div>
                </div>
                
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="text-sm text-gray-600 mb-1">{t('banks_count')}</div>
                  <div className="text-xl font-bold text-gray-900">
                    {kpiData.count}
                  </div>
                </div>
              </div>
            )}

            {/* Rates Table */}
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              {/* Table Header */}
              <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
                <div className="grid grid-cols-5 gap-4 text-sm font-medium text-gray-700">
                  <div>{t('bank')}</div>
                  <div className="text-center">{t('buy')}</div>
                  <div className="text-center">{t('sell')}</div>
                  <div className="text-center">{t('delta')}</div>
                  <div className="text-center">{t('updated')}</div>
                </div>
              </div>

              {/* Table Body */}
              <div className="divide-y divide-gray-200">
                {displayedRates.map((rate) => {
                  const buyRate = parseFloat(rate.buy);
                  const sellRate = parseFloat(rate.sell);
                  const delta = sellRate - buyRate;
                  
                  return (
                    <div key={rate.bank_id} className="px-4 py-3 hover:bg-gray-50">
                      <div className="grid grid-cols-5 gap-4 text-sm items-center">
                        <div className="font-medium text-gray-900 truncate">
                          {rate.bank_name}
                        </div>
                        <div className="text-center text-green-600 font-mono">
                          {formatNumber(buyRate)}
                        </div>
                        <div className="text-center text-red-600 font-mono font-semibold">
                          {formatNumber(sellRate)}
                        </div>
                        <div className="text-center text-gray-600 font-mono text-xs">
                          {formatNumber(delta)}
                        </div>
                        <div className="text-center text-xs text-gray-500">
                          {formatRelativeTime(rate.fetched_at)}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Show More/Less Button */}
            {bankRates.length > 10 && (
              <div className="text-center mt-4">
                <button
                  onClick={() => setShowAll(!showAll)}
                  className="px-6 py-3 bg-gray-100 text-gray-700 rounded-lg text-base font-medium hover:bg-gray-200 transition-colors border border-gray-300 min-h-[44px]"
                >
                  {showAll ? t('less') : t('more')}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}