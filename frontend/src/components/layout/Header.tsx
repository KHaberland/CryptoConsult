'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { MessageCircle, LayoutDashboard, TrendingUp, LogOut, User } from 'lucide-react'
import { useSessionStore } from '@/store/sessionStore'
import { APP_VERSION } from '@/version'

export function Header() {
  const pathname = usePathname()
  const router = useRouter()
  const { userName, resetSession } = useSessionStore()
  
  const isActive = (path: string) => pathname === path
  
  const handleLogout = () => {
    resetSession()
    router.push('/')
  }
  
  return (
    <header className="bg-white shadow-sm border-b">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <Link href="/dashboard" className="flex items-center">
            <TrendingUp className="w-8 h-8 text-primary-600 mr-2" />
            <span className="text-xl font-bold text-primary-600 hidden sm:inline">
              Крипто-Консультант
            </span>
            <span className="ml-2 text-xs text-gray-400 font-normal hidden sm:inline">v{APP_VERSION}</span>
          </Link>
          
          {/* Navigation */}
          <nav className="flex items-center space-x-1">
            <Link
              href="/dashboard"
              className={`flex items-center px-4 py-2 rounded-lg transition-colors ${
                isActive('/dashboard')
                  ? 'bg-primary-50 text-primary-600'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-primary-600'
              }`}
            >
              <LayoutDashboard className="w-5 h-5 mr-2" />
              <span className="hidden sm:inline">Дашборд</span>
            </Link>
            
            <Link
              href="/chat"
              className={`flex items-center px-4 py-2 rounded-lg transition-colors ${
                isActive('/chat')
                  ? 'bg-primary-50 text-primary-600'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-primary-600'
              }`}
            >
              <MessageCircle className="w-5 h-5 mr-2" />
              <span className="hidden sm:inline">Консультант</span>
            </Link>
            
            {/* User info */}
            <div className="flex items-center ml-4 pl-4 border-l">
              {userName && (
                <span className="flex items-center text-sm text-gray-600 mr-3">
                  <User className="w-4 h-4 mr-1" />
                  <span className="hidden sm:inline">{userName}</span>
                </span>
              )}
              <button
                onClick={handleLogout}
                className="flex items-center px-3 py-2 text-sm text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                title="Выйти"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </nav>
        </div>
      </div>
    </header>
  )
}
