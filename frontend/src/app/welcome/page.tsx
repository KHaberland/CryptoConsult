'use client'

import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { profileApi } from '@/services/api'
import { useSessionStore } from '@/store/sessionStore'
import { formatCurrency, formatPercent, formatDate } from '@/lib/utils'
import { 
  TrendingUp, 
  TrendingDown, 
  Calendar, 
  DollarSign,
  MessageCircle,
  LayoutDashboard,
  Loader2,
  AlertTriangle,
  CheckCircle,
  AlertCircle
} from 'lucide-react'

interface PortfolioData {
  name: string
  start_date: string
  initial_value: number
  current_value: number
  profit_loss: number
  profit_loss_percent: number
  days_active: number
}

interface Analysis {
  status: 'profit' | 'normal' | 'warning' | 'critical'
  icon: string
  title: string
  message: string
  recommendation: string
}

function WelcomeContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { userName, initSession, isReady } = useSessionStore()
  
  const [isLoading, setIsLoading] = useState(true)
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [displayName, setDisplayName] = useState<string>('')
  
  useEffect(() => {
    initSession()
  }, [initSession])
  
  useEffect(() => {
    if (!isReady) return
    
    const nameFromUrl = searchParams.get('name')
    const name = nameFromUrl || userName
    
    if (!name) {
      router.push('/login')
      return
    }
    
    setDisplayName(name)
    
    // Загружаем данные
    const fetchData = async () => {
      try {
        const data = await profileApi.lookup(name)
        setPortfolio(data.portfolio)
        setAnalysis(data.analysis)
      } catch (err) {
        // Если ошибка — отправляем на login
        router.push('/login')
      } finally {
        setIsLoading(false)
      }
    }
    
    fetchData()
  }, [isReady, userName, searchParams, router])
  
  const handleGoToConsultant = () => {
    router.push('/chat')
  }
  
  const handleGoToDashboard = () => {
    router.push('/dashboard')
  }
  
  // Определяем иконку и цвет для статуса
  const getStatusIcon = () => {
    if (!analysis) return null
    
    switch (analysis.status) {
      case 'profit':
        return <TrendingUp className="w-8 h-8 text-green-500" />
      case 'normal':
        return <CheckCircle className="w-8 h-8 text-blue-500" />
      case 'warning':
        return <AlertTriangle className="w-8 h-8 text-yellow-500" />
      case 'critical':
        return <AlertCircle className="w-8 h-8 text-red-500" />
      default:
        return null
    }
  }
  
  const getStatusColor = () => {
    if (!analysis) return 'bg-gray-50 border-gray-200'
    
    switch (analysis.status) {
      case 'profit':
        return 'bg-green-50 border-green-200'
      case 'normal':
        return 'bg-blue-50 border-blue-200'
      case 'warning':
        return 'bg-yellow-50 border-yellow-200'
      case 'critical':
        return 'bg-red-50 border-red-200'
      default:
        return 'bg-gray-50 border-gray-200'
    }
  }
  
  if (isLoading || !isReady) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-primary-50 to-white flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary-600 mx-auto mb-4" />
          <p className="text-gray-600">Загружаем ваши данные...</p>
        </div>
      </div>
    )
  }
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-white p-4">
      <div className="max-w-2xl mx-auto pt-8">
        {/* Приветствие */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Добрый день, {displayName}! 👋
          </h1>
          <p className="text-xl text-gray-600">
            Добро пожаловать!
          </p>
        </div>
        
        {/* Анализ портфеля */}
        {portfolio && analysis ? (
          <Card className="mb-6">
            <CardContent className="p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <TrendingUp className="w-5 h-5 mr-2 text-primary-600" />
                Анализ вашего портфеля
              </h2>
              
              {/* Информация о портфеле */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="flex items-center">
                  <Calendar className="w-5 h-5 text-gray-400 mr-2" />
                  <div>
                    <p className="text-xs text-gray-500">Портфель создан</p>
                    <p className="font-medium">{formatDate(portfolio.start_date)}</p>
                  </div>
                </div>
                <div className="flex items-center">
                  <DollarSign className="w-5 h-5 text-gray-400 mr-2" />
                  <div>
                    <p className="text-xs text-gray-500">Начальная стоимость</p>
                    <p className="font-medium">{formatCurrency(portfolio.initial_value)}</p>
                  </div>
                </div>
              </div>
              
              {/* Текущая стоимость */}
              <div className="bg-gray-50 rounded-lg p-4 mb-6">
                <p className="text-sm text-gray-500 mb-1">Текущая стоимость</p>
                <p className="text-3xl font-bold text-gray-900">
                  {formatCurrency(portfolio.current_value)}
                </p>
                <div className={`flex items-center mt-2 ${portfolio.profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {portfolio.profit_loss >= 0 ? (
                    <TrendingUp className="w-4 h-4 mr-1" />
                  ) : (
                    <TrendingDown className="w-4 h-4 mr-1" />
                  )}
                  <span className="font-medium">
                    {formatCurrency(portfolio.profit_loss)} ({formatPercent(portfolio.profit_loss_percent)})
                  </span>
                </div>
              </div>
              
              {/* Блок анализа */}
              <div className={`rounded-lg p-4 border-2 ${getStatusColor()}`}>
                <div className="flex items-start">
                  <div className="flex-shrink-0 mr-3">
                    {getStatusIcon()}
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900 mb-1">
                      {analysis.title}
                    </h3>
                    <p className="text-gray-700 mb-2">
                      {analysis.message}
                    </p>
                    <p className="text-sm text-gray-600">
                      💡 <strong>Рекомендация:</strong> {analysis.recommendation}
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card className="mb-6">
            <CardContent className="p-6 text-center text-gray-500">
              <p>Портфель не найден. Возможно, он был удалён.</p>
            </CardContent>
          </Card>
        )}
        
        {/* Вопрос */}
        <div className="text-center mb-6">
          <p className="text-lg text-gray-700 mb-4">
            Желаете получить консультацию?
          </p>
          
          <div className="flex justify-center gap-4">
            <Button
              onClick={handleGoToConsultant}
              className="px-8 py-3"
            >
              <MessageCircle className="w-5 h-5 mr-2" />
              Да, перейти к консультанту
            </Button>
            
            <Button
              variant="outline"
              onClick={handleGoToDashboard}
              className="px-8 py-3"
            >
              <LayoutDashboard className="w-5 h-5 mr-2" />
              Нет, в дашборд
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function WelcomePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gradient-to-br from-primary-50 to-white flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary-600 mx-auto mb-4" />
          <p className="text-gray-600">Загрузка...</p>
        </div>
      </div>
    }>
      <WelcomeContent />
    </Suspense>
  )
}
