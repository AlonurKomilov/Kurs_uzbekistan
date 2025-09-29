'use client';

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import '../i18n';

interface Rate {
  currency: string;
  rate: number;
}

export default function HomePage() {
  const { t, i18n } = useTranslation();
  const [rates, setRates] = useState<Rate[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Initialize Telegram WebApp
    if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
      const tg = window.Telegram.WebApp;
      tg.ready();
      tg.expand();
      
      // Set theme
      document.documentElement.style.setProperty('--tg-theme-bg-color', tg.themeParams.bg_color);
      document.documentElement.style.setProperty('--tg-theme-text-color', tg.themeParams.text_color);
    }

    // Fetch rates
    fetchRates();
  }, []);

  const fetchRates = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/rates`);
      const data = await response.json();
      
      const ratesList = Object.entries(data.rates).map(([currency, rate]) => ({
        currency,
        rate: rate as number,
      }));
      
      setRates(ratesList);
    } catch (error) {
      console.error('Failed to fetch rates:', error);
    } finally {
      setLoading(false);
    }
  };

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
  };

  if (loading) {
    return (
      <div className="container">
        <div className="loading">{t('loading')}</div>
      </div>
    );
  }

  return (
    <div className="container">
      <header className="header">
        <h1>{t('title')}</h1>
        <div className="language-selector">
          <button onClick={() => changeLanguage('en')}>EN</button>
          <button onClick={() => changeLanguage('ru')}>RU</button>
          <button onClick={() => changeLanguage('uz_cy')}>O'Z</button>
        </div>
      </header>

      <main className="main">
        <div className="rates-grid">
          {rates.map((rate) => (
            <div key={rate.currency} className="rate-card">
              <div className="currency">{rate.currency}</div>
              <div className="rate">{rate.rate.toLocaleString()}</div>
            </div>
          ))}
        </div>
      </main>

      <style jsx>{`
        .container {
          min-height: 100vh;
          padding: 20px;
          background-color: var(--tg-theme-bg-color, #ffffff);
          color: var(--tg-theme-text-color, #000000);
        }
        
        .header {
          text-align: center;
          margin-bottom: 30px;
        }
        
        .header h1 {
          margin: 0 0 20px 0;
          font-size: 24px;
          font-weight: bold;
        }
        
        .language-selector {
          display: flex;
          gap: 10px;
          justify-content: center;
        }
        
        .language-selector button {
          padding: 8px 16px;
          border: 1px solid #ddd;
          background: transparent;
          border-radius: 6px;
          cursor: pointer;
        }
        
        .rates-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 16px;
        }
        
        .rate-card {
          padding: 16px;
          border: 1px solid #ddd;
          border-radius: 8px;
          text-align: center;
        }
        
        .currency {
          font-size: 18px;
          font-weight: bold;
          margin-bottom: 8px;
        }
        
        .rate {
          font-size: 16px;
          color: #666;
        }
        
        .loading {
          text-align: center;
          padding: 50px;
          font-size: 18px;
        }
      `}</style>
    </div>
  );
}