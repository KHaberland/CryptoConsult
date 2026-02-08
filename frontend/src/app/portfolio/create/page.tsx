'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useSessionStore } from '@/store/sessionStore'
import { usePortfolioStore } from '@/store/portfolioStore'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Alert } from '@/components/ui/Alert'
import { portfolioApi } from '@/services/api'
import { 
  TrendingUp, 
  Plus, 
  Trash2, 
  PieChart,
  Loader2,
  CheckCircle,
  Sparkles,
  X,
  ArrowRight
} from 'lucide-react'

// Доступные криптовалюты с характеристиками для AI-анализа
const AVAILABLE_COINS = [
  { symbol: 'BTC', name: 'Bitcoin', stability: 'высокая', volatility: 'умеренная', description: 'Главная криптовалюта, цифровое золото' },
  { symbol: 'ETH', name: 'Ethereum', stability: 'высокая', volatility: 'умеренная', description: 'Платформа смарт-контрактов №1' },
  { symbol: 'BNB', name: 'Binance Coin', stability: 'средняя', volatility: 'умеренная', description: 'Токен крупнейшей биржи' },
  { symbol: 'SOL', name: 'Solana', stability: 'средняя', volatility: 'высокая', description: 'Быстрый блокчейн для DeFi' },
  { symbol: 'XRP', name: 'Ripple', stability: 'средняя', volatility: 'высокая', description: 'Токен для банковских переводов' },
  { symbol: 'ADA', name: 'Cardano', stability: 'средняя', volatility: 'высокая', description: 'Научный подход к блокчейну' },
  { symbol: 'DOGE', name: 'Dogecoin', stability: 'низкая', volatility: 'очень высокая', description: 'Мем-монета с высоким риском' },
  { symbol: 'DOT', name: 'Polkadot', stability: 'средняя', volatility: 'высокая', description: 'Мультичейн экосистема' },
  { symbol: 'MATIC', name: 'Polygon', stability: 'средняя', volatility: 'высокая', description: 'Решение масштабирования Ethereum' },
  { symbol: 'LINK', name: 'Chainlink', stability: 'средняя', volatility: 'высокая', description: 'Оракулы для смарт-контрактов' },
  { symbol: 'ATOM', name: 'Cosmos', stability: 'средняя', volatility: 'высокая', description: 'Интернет блокчейнов' },
  { symbol: 'LTC', name: 'Litecoin', stability: 'средняя', volatility: 'умеренная', description: 'Цифровое серебро' },
  { symbol: 'UNI', name: 'Uniswap', stability: 'средняя', volatility: 'высокая', description: 'Лидер децентрализованных бирж' },
  { symbol: 'AVAX', name: 'Avalanche', stability: 'средняя', volatility: 'высокая', description: 'Быстрый конкурент Ethereum' },
  { symbol: 'TRX', name: 'TRON', stability: 'средняя', volatility: 'умеренная', description: 'Платформа для контента' },
  { symbol: 'USDT', name: 'Tether (стейблкоин)', stability: 'очень высокая', volatility: 'минимальная', description: 'Стейблкоин привязанный к доллару' },
  { symbol: 'USDC', name: 'USD Coin (стейблкоин)', stability: 'очень высокая', volatility: 'минимальная', description: 'Регулируемый стейблкоин' },
]

// Генерация AI-комментария для монеты
const generateCoinAnalysis = (symbol: string, percentage: number): string => {
  const coin = AVAILABLE_COINS.find(c => c.symbol === symbol)
  if (!coin) return ''
  
  // Оценка объёма в портфеле
  let volumeComment = ''
  if (percentage >= 40) {
    volumeComment = 'Крупная доля — высокая зависимость от этого актива.'
  } else if (percentage >= 20) {
    volumeComment = 'Хороший объём для диверсификации.'
  } else if (percentage >= 10) {
    volumeComment = 'Достаточный объём для баланса.'
  } else if (percentage >= 5) {
    volumeComment = 'Небольшая доля — минимальное влияние на портфель.'
  } else {
    volumeComment = 'Очень маленькая доля — почти не влияет на результат.'
  }
  
  // Комментарий по характеристикам
  let riskComment = ''
  if (coin.stability === 'очень высокая') {
    riskComment = 'Стабильный актив для сохранения капитала.'
  } else if (coin.stability === 'высокая') {
    riskComment = `${coin.description}. Стабильность ${coin.stability}, волатильность ${coin.volatility}.`
  } else if (coin.volatility === 'очень высокая') {
    riskComment = `${coin.description}. Высокий риск — подходит для спекуляций.`
  } else {
    riskComment = `${coin.description}. Волатильность ${coin.volatility}.`
  }
  
  return `${riskComment} ${volumeComment}`
}

interface Asset {
  symbol: string
  name: string
  percentage: number
}

export default function CreatePortfolioPage() {
  const router = useRouter()
  const { initSession, isReady } = useSessionStore()
  const { profile, fetchProfile } = usePortfolioStore()
  
  const [assets, setAssets] = useState<Asset[]>([
    { symbol: 'BTC', name: 'Bitcoin', percentage: 50 },
    { symbol: 'ETH', name: 'Ethereum', percentage: 30 },
  ])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showAnalysis, setShowAnalysis] = useState(false)
  const [createdAssets, setCreatedAssets] = useState<Asset[]>([])
  
  useEffect(() => {
    initSession()
  }, [initSession])
  
  useEffect(() => {
    if (isReady) {
      fetchProfile()
    }
  }, [isReady, fetchProfile])
  
  const totalPercentage = assets.reduce((sum, a) => sum + a.percentage, 0)
  const isValid = totalPercentage === 100 && assets.length > 0
  
  const addAsset = () => {
    // Найти первую монету, которой ещё нет в списке
    const usedSymbols = new Set(assets.map(a => a.symbol))
    const availableCoin = AVAILABLE_COINS.find(c => !usedSymbols.has(c.symbol))
    
    if (availableCoin) {
      setAssets([...assets, { ...availableCoin, percentage: 0 }])
    }
  }
  
  const removeAsset = (index: number) => {
    setAssets(assets.filter((_, i) => i !== index))
  }
  
  const updateAsset = (index: number, field: 'symbol' | 'percentage', value: string | number) => {
    const newAssets = [...assets]
    if (field === 'symbol') {
      const coin = AVAILABLE_COINS.find(c => c.symbol === value)
      if (coin) {
        newAssets[index] = { ...newAssets[index], symbol: coin.symbol, name: coin.name }
      }
    } else {
      newAssets[index] = { ...newAssets[index], percentage: Number(value) }
    }
    setAssets(newAssets)
  }
  
  const handleSubmit = async () => {
    if (!isValid || !profile) return
    
    setIsSubmitting(true)
    setError(null)
    
    try {
      await portfolioApi.create({
        name: 'Мой портфель',
        initial_amount: Number(profile.investment_amount),
        target_years: profile.investment_horizon,
        use_default_assets: false,
        custom_assets: assets.map(a => ({
          symbol: a.symbol,
          name: a.name,
          percentage: a.percentage,
        })),
      })
      
      // Сохраняем созданные активы и показываем анализ
      setCreatedAssets([...assets])
      setShowAnalysis(true)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка создания портфеля')
    } finally {
      setIsSubmitting(false)
    }
  }
  
  const handleGoToDashboard = () => {
    router.push('/dashboard')
  }
  
  if (!isReady) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-white">
        <Loader2 className="w-12 h-12 animate-spin text-primary-600" />
      </div>
    )
  }
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-white p-4">
      {/* Модальное окно с AI-анализом */}
      {showAnalysis && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            {/* Header */}
            <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
              <div className="flex items-center">
                <Sparkles className="w-6 h-6 text-yellow-500 mr-2" />
                <h2 className="text-xl font-bold text-gray-900">
                  Портфель создан!
                </h2>
              </div>
              <button
                onClick={handleGoToDashboard}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            
            {/* Content */}
            <div className="p-6">
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
                <p className="text-green-800 font-medium text-center">
                  🎉 Поздравляем! Ваш портфель успешно создан.
                </p>
                <p className="text-green-700 text-sm text-center mt-1">
                  Сумма инвестиций: ${profile?.investment_amount?.toLocaleString()}
                </p>
              </div>
              
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <PieChart className="w-5 h-5 mr-2 text-primary-600" />
                AI-анализ вашего портфеля
              </h3>
              
              <div className="space-y-4">
                {createdAssets.map((asset, index) => {
                  const coin = AVAILABLE_COINS.find(c => c.symbol === asset.symbol)
                  const analysis = generateCoinAnalysis(asset.symbol, asset.percentage)
                  
                  return (
                    <div key={index} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center">
                          <span className="font-bold text-gray-900 mr-2">
                            {asset.symbol}
                          </span>
                          <span className="text-gray-500 text-sm">
                            {asset.name}
                          </span>
                        </div>
                        <span className="text-lg font-bold text-primary-600">
                          {asset.percentage}%
                        </span>
                      </div>
                      
                      {/* Характеристики */}
                      {coin && (
                        <div className="flex gap-2 mb-2">
                          <span className={`text-xs px-2 py-1 rounded ${
                            coin.stability === 'очень высокая' ? 'bg-green-100 text-green-700' :
                            coin.stability === 'высокая' ? 'bg-blue-100 text-blue-700' :
                            coin.stability === 'средняя' ? 'bg-yellow-100 text-yellow-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                            Стабильность: {coin.stability}
                          </span>
                          <span className={`text-xs px-2 py-1 rounded ${
                            coin.volatility === 'минимальная' ? 'bg-green-100 text-green-700' :
                            coin.volatility === 'умеренная' ? 'bg-blue-100 text-blue-700' :
                            coin.volatility === 'высокая' ? 'bg-yellow-100 text-yellow-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                            Волатильность: {coin.volatility}
                          </span>
                        </div>
                      )}
                      
                      {/* AI комментарий */}
                      <p className="text-gray-600 text-sm">
                        💡 {analysis}
                      </p>
                    </div>
                  )
                })}
              </div>
              
              {/* Общая рекомендация */}
              <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-blue-800 text-sm">
                  <strong>📊 Общая оценка:</strong> {
                    createdAssets.some(a => a.symbol === 'USDT' || a.symbol === 'USDC')
                      ? 'Хорошо, что вы включили стейблкоины — они снижают волатильность.'
                      : 'Рекомендуем добавить 5-10% стейблкоинов для снижения волатильности.'
                  } {
                    createdAssets.find(a => a.symbol === 'BTC')?.percentage >= 30
                      ? 'Bitcoin как основа портфеля — разумный выбор.'
                      : createdAssets.find(a => a.symbol === 'BTC')
                        ? 'Доля Bitcoin невелика — рассмотрите увеличение для стабильности.'
                        : 'Отсутствие Bitcoin повышает риск портфеля.'
                  }
                </p>
              </div>
            </div>
            
            {/* Footer */}
            <div className="sticky bottom-0 bg-white border-t px-6 py-4">
              <Button
                onClick={handleGoToDashboard}
                className="w-full"
              >
                Перейти в дашборд
                <ArrowRight className="w-5 h-5 ml-2" />
              </Button>
            </div>
          </div>
        </div>
      )}
      
      <div className="max-w-2xl mx-auto pt-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-2">
            <TrendingUp className="w-10 h-10 text-primary-600 mr-2" />
            <h1 className="text-2xl font-bold text-primary-600">
              Крипто-Консультант
            </h1>
          </div>
          <p className="text-gray-600">Создание портфеля</p>
        </div>
        
        {error && (
          <Alert variant="error" className="mb-4">
            {error}
          </Alert>
        )}
        
        {/* Info */}
        <Card className="mb-6 border-blue-200 bg-blue-50">
          <CardContent className="py-4">
            <div className="flex items-start">
              <PieChart className="w-5 h-5 text-blue-600 mr-3 mt-0.5" />
              <div>
                <p className="text-blue-800 font-medium">
                  Сумма инвестиций: ${profile?.investment_amount?.toLocaleString() || '—'}
                </p>
                <p className="text-blue-700 text-sm mt-1">
                  Распределите 100% между выбранными активами
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        {/* Assets */}
        <Card className="mb-6">
          <CardContent>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Состав портфеля
            </h2>
            
            <div className="space-y-3">
              {assets.map((asset, index) => (
                <div key={index} className="flex items-center gap-3">
                  <select
                    value={asset.symbol}
                    onChange={(e) => updateAsset(index, 'symbol', e.target.value)}
                    className="flex-1 p-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  >
                    {AVAILABLE_COINS.map(coin => (
                      <option 
                        key={coin.symbol} 
                        value={coin.symbol}
                        disabled={assets.some((a, i) => i !== index && a.symbol === coin.symbol)}
                      >
                        {coin.symbol} - {coin.name}
                      </option>
                    ))}
                  </select>
                  
                  <div className="flex items-center w-24">
                    <Input
                      type="number"
                      value={asset.percentage}
                      onChange={(e) => updateAsset(index, 'percentage', e.target.value)}
                      min={0}
                      max={100}
                      className="text-center"
                    />
                    <span className="ml-1 text-gray-500">%</span>
                  </div>
                  
                  <button
                    onClick={() => removeAsset(index)}
                    className="p-2 text-red-500 hover:bg-red-50 rounded-lg"
                    disabled={assets.length <= 1}
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                </div>
              ))}
            </div>
            
            {assets.length < AVAILABLE_COINS.length && (
              <button
                onClick={addAsset}
                className="mt-4 flex items-center text-primary-600 hover:text-primary-700"
              >
                <Plus className="w-5 h-5 mr-1" />
                Добавить актив
              </button>
            )}
          </CardContent>
        </Card>
        
        {/* Total */}
        <Card className={`mb-6 ${isValid ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <span className={isValid ? 'text-green-800' : 'text-red-800'}>
                Итого:
              </span>
              <div className="flex items-center">
                <span className={`text-xl font-bold ${isValid ? 'text-green-800' : 'text-red-800'}`}>
                  {totalPercentage}%
                </span>
                {isValid && <CheckCircle className="w-5 h-5 text-green-600 ml-2" />}
              </div>
            </div>
            {!isValid && (
              <p className="text-red-700 text-sm mt-1">
                {totalPercentage < 100 
                  ? `Нужно добавить ещё ${100 - totalPercentage}%`
                  : `Уберите ${totalPercentage - 100}%`
                }
              </p>
            )}
          </CardContent>
        </Card>
        
        {/* Submit */}
        <Button
          onClick={handleSubmit}
          className="w-full py-4"
          disabled={!isValid || isSubmitting}
          isLoading={isSubmitting}
        >
          Создать портфель
        </Button>
      </div>
    </div>
  )
}
