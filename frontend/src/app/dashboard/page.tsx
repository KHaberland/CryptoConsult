'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useSessionStore } from '@/store/sessionStore'
import { usePortfolioStore } from '@/store/portfolioStore'
import { Header } from '@/components/layout/Header'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/Alert'
import { Progress } from '@/components/ui/Progress'
import { ContributeModal } from '@/components/portfolio/ContributeModal'
import { WithdrawModal } from '@/components/portfolio/WithdrawModal'
import { formatCurrency, formatPercent, formatDate } from '@/lib/utils'
import {
  TrendingUp,
  TrendingDown,
  Calendar,
  Target,
  RefreshCw,
  CheckCircle,
  CalendarClock,
  PlusCircle,
  Wallet,
} from 'lucide-react'
import { getDcaEntriesWithCumulative } from '@/lib/dca'

export default function DashboardPage() {
  const router = useRouter()
  const [showContributeModal, setShowContributeModal] = useState(false)
  const [showWithdrawModal, setShowWithdrawModal] = useState(false)
  const { initSession, isReady } = useSessionStore()
  const {
    portfolioValue,
    profile,
    hasPortfolio,
    hasProfile,
    isLoading,
    error,
    fetchPortfolioValue,
    fetchProfile,
    contribute,
    withdraw,
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
  
  const progressPercent = portfolioValue.days_active / (portfolioValue.days_active + portfolioValue.days_remaining) * 100

  // Данные из бэкенда — актуальные (учитывают все взносы)
  const investedSoFar = portfolioValue.initial_value
  const totalInvestment = Number(profile?.investment_amount ?? portfolioValue.initial_value ?? 0)
  const showDcaBreakdown = (profile?.use_dca && (profile.experience_level === 'beginner' ? 3 : (profile.dca_parts ?? 4)) > 1) ?? false
  const parts = profile?.use_dca ? (profile.experience_level === 'beginner' ? 3 : (profile.dca_parts ?? 4)) : 1
  const amount = profile?.investment_amount ?? portfolioValue.initial_value ?? 0
  const startDate = portfolioValue.start_date ? new Date(portfolioValue.start_date) : new Date()
  const dcaEntries = getDcaEntriesWithCumulative(parts, Number(amount), startDate, new Date())

  // Количество выполненных входов: начальный + взносы
  const contributionsCount = portfolioValue.contributions?.length ?? 0
  const doneEntriesCount = Math.min(1 + contributionsCount, parts)

  // Рекомендуемая сумма следующего взноса (при DCA)
  const remaining = totalInvestment - investedSoFar
  const remainingParts = Math.max(0, parts - doneEntriesCount)
  const suggestedAmount = remainingParts > 0 && remaining > 0
    ? Math.round((remaining / remainingParts) * 100) / 100
    : 0

  const displayAssets = portfolioValue.assets
  const displayTotalValue = portfolioValue.total_value
  const displayProfitLoss = portfolioValue.profit_loss
  const displayProfitLossPercent = portfolioValue.profit_loss_percent
  const isProfit = portfolioValue.profit_loss >= 0

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
                    {formatCurrency(displayTotalValue)}
                  </p>
                  {(showDcaBreakdown || totalInvestment > investedSoFar) && (
                    <p className="text-sm text-gray-500 mt-1">
                      Вложено: {formatCurrency(investedSoFar)}
                      {totalInvestment > 0 && ` из ${formatCurrency(totalInvestment)}`}
                    </p>
                  )}
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
                      {formatCurrency(displayProfitLoss)}
                    </span>
                    <span className={`ml-2 text-lg ${isProfit ? 'text-green-600' : 'text-red-600'}`}>
                      ({formatPercent(displayProfitLossPercent)})
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 mt-1">
                    Стоимость: {formatCurrency(displayTotalValue)}
                  </p>
                </div>
              </div>

              {/* Разбивка по датам входа (DCA) */}
              {showDcaBreakdown && (
                <div className="mt-6 pt-6 border-t border-gray-200">
                  <div className="flex items-center gap-2 mb-3">
                    <CalendarClock className="w-5 h-5 text-primary-600" />
                    <span className="font-semibold text-gray-900">Разбивка по входам</span>
                  </div>
                  <p className="text-sm text-gray-600 mb-3">
                    По мере наступления даты взноса к портфелю добавляется сумма.
                  </p>
                  <div className="overflow-x-auto rounded-lg border border-gray-200">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-gray-50 border-b border-gray-200">
                          <th className="px-4 py-2 text-left font-medium text-gray-700">Вход</th>
                          <th className="px-4 py-2 text-left font-medium text-gray-700">Дата</th>
                          <th className="px-4 py-2 text-right font-medium text-gray-700">Сумма</th>
                          <th className="px-4 py-2 text-right font-medium text-gray-700">Стоимость после входа</th>
                          <th className="px-4 py-2 text-center font-medium text-gray-700 w-24">Статус</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dcaEntries.map((e) => {
                          const isDone = e.entryNumber <= doneEntriesCount
                          return (
                            <tr
                              key={e.entryNumber}
                              className={`border-b border-gray-100 last:border-0 ${
                                isDone ? 'bg-primary-50/50' : ''
                              }`}
                            >
                              <td className="px-4 py-2 font-medium text-gray-900">Вход {e.entryNumber}</td>
                              <td className="px-4 py-2 text-gray-700">{e.dateStr}</td>
                              <td className="px-4 py-2 text-right font-medium">
                                {formatCurrency(e.amountPerEntry)}
                              </td>
                              <td className="px-4 py-2 text-right font-semibold text-primary-600">
                                {formatCurrency(e.cumulativeAmount)}
                              </td>
                              <td className="px-4 py-2 text-center">
                                {isDone ? (
                                  <span className="inline-flex items-center gap-1 text-xs font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full">
                                    <CheckCircle className="w-3.5 h-3.5" />
                                    Выполнено
                                  </span>
                                ) : (
                                  <span className="text-xs text-gray-500">Запланировано</span>
                                )}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">
                    Итого будет вложено: {formatCurrency(dcaEntries[dcaEntries.length - 1]?.cumulativeAmount ?? 0)}
                  </p>
                  {remainingParts > 0 && (
                    <Button
                      variant="primary"
                      size="sm"
                      className="mt-3"
                      onClick={() => setShowContributeModal(true)}
                    >
                      <PlusCircle className="w-4 h-4 mr-1" />
                      Внести взнос
                    </Button>
                  )}
                </div>
              )}
              
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
              <Link href="/chat?cmd=recommendation" className="block">
                <Button className="w-full" variant="primary">
                  Получить рекомендацию
                </Button>
              </Link>
              <Link href="/chat?cmd=status" className="block">
                <Button className="w-full" variant="secondary">
                  Статус портфеля
                </Button>
              </Link>
              {(totalInvestment > investedSoFar || !showDcaBreakdown) && (
                <Button
                  className="w-full"
                  variant="secondary"
                  onClick={() => setShowContributeModal(true)}
                >
                  <PlusCircle className="w-4 h-4 mr-1" />
                  Внести взнос
                </Button>
              )}
              <Button
                className="w-full"
                variant="secondary"
                onClick={() => setShowWithdrawModal(true)}
              >
                <Wallet className="w-4 h-4 mr-1" />
                Вывод средств
              </Button>
            </CardContent>
          </Card>
        </div>
        
        {/* Assets Table */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Состав портфеля</CardTitle>
            {showDcaBreakdown && (
              <span className="text-sm text-gray-500 font-normal">
                На сегодня ({formatCurrency(investedSoFar)} из {formatCurrency(totalInvestment)})
              </span>
            )}
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
                  {(showDcaBreakdown ? displayAssets : portfolioValue.assets).map((asset) => (
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

      <ContributeModal
        isOpen={showContributeModal}
        onClose={() => setShowContributeModal(false)}
        onConfirm={async (amt) => {
          await contribute(amt)
        }}
        investedSoFar={investedSoFar}
        totalPlanned={totalInvestment > 0 ? totalInvestment : undefined}
        suggestedAmount={suggestedAmount}
      />
      <WithdrawModal
        isOpen={showWithdrawModal}
        onClose={() => setShowWithdrawModal(false)}
        onConfirm={async (assets) => {
          await withdraw(assets)
        }}
        totalValue={displayTotalValue}
      />
    </div>
  )
}
