'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useSessionStore } from '@/store/sessionStore'
import { usePortfolioStore } from '@/store/portfolioStore'
import { Header } from '@/components/layout/Header'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/Alert'
import { Progress } from '@/components/ui/Progress'
import { formatCurrency, formatPercent, formatDate } from '@/lib/utils'
import {
  TrendingUp,
  TrendingDown,
  Calendar,
  Target,
  MessageCircle,
  RefreshCw,
} from 'lucide-react'

export default function DashboardPage() {
  const router = useRouter()
  const { initSession, isReady } = useSessionStore()
  const {
    portfolioValue,
    hasPortfolio,
    hasProfile,
    isLoading,
    error,
    fetchPortfolioValue,
    fetchProfile,
  } = usePortfolioStore()
  
  // Инициализация сессии
  useEffect(() => {
    initSession()
  }, [initSession])
  
  // Загрузка данных после инициализации сессии
  useEffect(() => {
    if (isReady) {
      fetchProfile()
      fetchPortfolioValue()
    }
  }, [isReady, fetchProfile, fetchPortfolioValue])
  
  // Если нет профиля — редирект на анкету
  useEffect(() => {
    if (isReady && !isLoading && !hasProfile) {
      router.push('/questionnaire')
    }
  }, [hasProfile, isLoading, isReady, router])
  
  // Если нет портфеля — редирект на анкету
  useEffect(() => {
    if (isReady && !isLoading && hasProfile && !hasPortfolio) {
      router.push('/questionnaire')
    }
  }, [hasPortfolio, hasProfile, isLoading, isReady, router])
  
  const handleRefresh = () => {
    fetchPortfolioValue(true) // force = true для ручного обновления
  }
  
  if (!isReady || isLoading || !portfolioValue) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="flex items-center justify-center h-[calc(100vh-64px)]">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-600"></div>
        </div>
      </div>
    )
  }
  
  const isProfit = portfolioValue.profit_loss >= 0
  const progressPercent = portfolioValue.days_active / (portfolioValue.days_active + portfolioValue.days_remaining) * 100
  
  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <Alert variant="error" className="mb-6">
            {error}
          </Alert>
        )}
        
        {/* Portfolio Summary */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* Total Value Card */}
          <Card className="lg:col-span-2">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Мой портфель</CardTitle>
              <Button variant="secondary" size="sm" onClick={handleRefresh}>
                <RefreshCw className="w-4 h-4 mr-1" />
                Обновить
              </Button>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <p className="text-sm text-gray-600">Текущая стоимость</p>
                  <p className="text-3xl font-bold text-gray-900">
                    {formatCurrency(portfolioValue.total_value)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Прибыль / Убыток</p>
                  <div className="flex items-center">
                    {isProfit ? (
                      <TrendingUp className="w-6 h-6 text-green-500 mr-2" />
                    ) : (
                      <TrendingDown className="w-6 h-6 text-red-500 mr-2" />
                    )}
                    <span className={`text-2xl font-bold ${isProfit ? 'text-green-600' : 'text-red-600'}`}>
                      {formatCurrency(portfolioValue.profit_loss)}
                    </span>
                    <span className={`ml-2 text-lg ${isProfit ? 'text-green-600' : 'text-red-600'}`}>
                      ({formatPercent(portfolioValue.profit_loss_percent)})
                    </span>
                  </div>
                </div>
              </div>
              
              {/* Timeline */}
              <div className="mt-6 pt-6 border-t">
                <div className="flex justify-between text-sm text-gray-600 mb-2">
                  <div className="flex items-center">
                    <Calendar className="w-4 h-4 mr-1" />
                    <span>Начало: {formatDate(portfolioValue.start_date)}</span>
                  </div>
                  <div className="flex items-center">
                    <Target className="w-4 h-4 mr-1" />
                    <span>Цель: {formatDate(portfolioValue.target_date)}</span>
                  </div>
                </div>
                <Progress value={progressPercent} showLabel />
                <p className="text-sm text-gray-500 mt-1 text-center">
                  {portfolioValue.days_active} дней активен • {portfolioValue.days_remaining} дней осталось
                </p>
              </div>
            </CardContent>
          </Card>
          
          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Быстрые действия</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Link href="/chat" className="block">
                <Button className="w-full" variant="primary">
                  <MessageCircle className="w-4 h-4 mr-2" />
                  Консультация
                </Button>
              </Link>
              <Link href="/chat?cmd=status" className="block">
                <Button className="w-full" variant="secondary">
                  Статус портфеля
                </Button>
              </Link>
              <Link href="/chat?cmd=recommendation" className="block">
                <Button className="w-full" variant="secondary">
                  Получить рекомендацию
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
        
        {/* Assets Table */}
        <Card>
          <CardHeader>
            <CardTitle>Состав портфеля</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-sm text-gray-600 border-b">
                    <th className="pb-3 font-medium">Актив</th>
                    <th className="pb-3 font-medium text-right">Доля</th>
                    <th className="pb-3 font-medium text-right">Цена</th>
                    <th className="pb-3 font-medium text-right">24ч</th>
                    <th className="pb-3 font-medium text-right">Стоимость</th>
                    <th className="pb-3 font-medium text-right">P/L</th>
                  </tr>
                </thead>
                <tbody>
                  {portfolioValue.assets.map((asset) => (
                    <tr key={asset.symbol} className="border-b last:border-0">
                      <td className="py-4">
                        <div className="flex items-center">
                          <div className="w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center mr-3">
                            <span className="text-xs font-bold text-primary-600">
                              {asset.symbol.slice(0, 2)}
                            </span>
                          </div>
                          <div>
                            <p className="font-medium text-gray-900">{asset.symbol}</p>
                            <p className="text-sm text-gray-500">{asset.name}</p>
                          </div>
                        </div>
                      </td>
                      <td className="py-4 text-right">
                        <span className="text-gray-900">{asset.percentage}%</span>
                      </td>
                      <td className="py-4 text-right">
                        <span className="text-gray-900">
                          {formatCurrency(asset.current_price)}
                        </span>
                      </td>
                      <td className="py-4 text-right">
                        <span className={asset.change_24h >= 0 ? 'text-green-600' : 'text-red-600'}>
                          {formatPercent(asset.change_24h)}
                        </span>
                      </td>
                      <td className="py-4 text-right">
                        <span className="text-gray-900 font-medium">
                          {formatCurrency(asset.current_value)}
                        </span>
                      </td>
                      <td className="py-4 text-right">
                        <div className={asset.profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}>
                          <span className="font-medium">
                            {formatCurrency(asset.profit_loss)}
                          </span>
                          <span className="text-sm ml-1">
                            ({formatPercent(asset.profit_loss_percent)})
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
