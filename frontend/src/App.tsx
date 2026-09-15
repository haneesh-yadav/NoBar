import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { AuthProvider } from './context/AuthContext';
import { UploadPage } from './pages/UploadPage';
import { DocumentViewerPage } from './pages/DocumentViewerPage';
import { LibraryPage } from './pages/LibraryPage';
import { ReviewQueuePage } from './pages/ReviewQueuePage';
import { AuthPage } from './pages/AuthPage';
import { ProfilePage } from './pages/ProfilePage';

export const App: React.FC = () => {
  const [highContrast, setHighContrast] = useState<boolean>(() => {
    return localStorage.getItem('nobar_high_contrast') === 'true';
  });
  const [fontSize, setFontSize] = useState<string>(() => {
    return localStorage.getItem('nobar_font_size') || 'font-size-md';
  });
  const [language, setLanguage] = useState<string>('en');

  // Sync high contrast mode to <html> tag
  useEffect(() => {
    localStorage.setItem('nobar_high_contrast', String(highContrast));
    if (highContrast) {
      document.documentElement.classList.add('high-contrast');
    } else {
      document.documentElement.classList.remove('high-contrast');
    }
  }, [highContrast]);

  // Sync font size class to <body> tag
  useEffect(() => {
    localStorage.setItem('nobar_font_size', fontSize);
    document.body.className = fontSize;
  }, [fontSize]);

  // Initialize axe-core accessibility auditor in dev
  useEffect(() => {
    if (import.meta.env.DEV) {
      import('@axe-core/react').then((axe) => {
        axe.default(React, (window as any).ReactDOM || {}, 1000);
      }).catch(() => {});
    }
  }, []);

  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
          <Navbar
            highContrast={highContrast}
            setHighContrast={setHighContrast}
            fontSize={fontSize}
            setFontSize={setFontSize}
            language={language}
            setLanguage={setLanguage}
          />

          <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6" role="main">
            <Routes>
              <Route path="/" element={<LibraryPage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/library" element={<LibraryPage />} />
              <Route path="/document/:id" element={<DocumentViewerPage language={language} setLanguage={setLanguage} />} />
              <Route path="/review" element={<ReviewQueuePage />} />
              <Route path="/auth/login" element={<AuthPage mode="login" />} />
              <Route path="/auth/register" element={<AuthPage mode="register" />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>

          <footer className="bg-slate-900 border-t border-slate-800 text-xs text-slate-500 py-6 text-center">
            <div className="max-w-7xl mx-auto px-4 space-y-2">
              <p className="font-semibold text-slate-400">
                NoBar — AI Accessibility Auditor for Government/NGO Welfare Scheme Documents
              </p>
              <p>
                Built for Block Convey "Money Talks: AI x Finance" Hackathon • Verified WCAG 2.1 AA & PRISM Traced
              </p>
            </div>
          </footer>
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
