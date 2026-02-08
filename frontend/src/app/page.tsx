'use client'

import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { TrendingUp, Shield, BarChart3, MessageCircle, ArrowRight } from 'lucide-react'

export default function Home() {
  const router = useRouter()
  
  const handleStart = () => {
    router.push('/login')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-blue-50">
      {/* Hero Section */}
      <div className="max-w-4xl mx-auto px-4 py-16">
        <div className="text-center mb-12">
          {/* Logo */}
          <div className="inline-flex items-center justify-center w-20 h-20 bg-primary-100 rounded-2xl mb-6">
            <TrendingUp className="w-10 h-10 text-primary-600" />
          </div>
          
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            Крипто-Консультант
          </h1>
          
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Ваш персональный помощник для долгосрочных и безопасных инвестиций в криптовалюты
          </p>
        </div>
        
        {/* Features */}
        <div className="grid md:grid-cols-3 gap-6 mb-12">
          <div className="bg-white rounded-2xl p-6 shadow-lg">
            <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center mb-4">
              <BarChart3 className="w-6 h-6 text-green-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">
              Анализ портфеля
            </h3>
            <p className="text-gray-600 text-sm">
              Следите за тем, как распределены ваши инвестиции, и получайте информацию о ключевых рисках и колебаниях цен — всё в реальном времени.
            </p>
          </div>
          
          <div className="bg-white rounded-2xl p-6 shadow-lg">
            <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center mb-4">
              <Shield className="w-6 h-6 text-blue-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">
              Контроль рисков
            </h3>
            <p className="text-gray-600 text-sm">
              Консервативная стратегия с мониторингом значимых изменений рынка и предупреждениями о возможных просадках.
            </p>
          </div>
          
          <div className="bg-white rounded-2xl p-6 shadow-lg">
            <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center mb-4">
              <MessageCircle className="w-6 h-6 text-purple-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">
              AI Консультант
            </h3>
            <p className="text-gray-600 text-sm">
              Получайте советы и рекомендации, чтобы принимать обдуманные инвестиционные решения. <span className="font-semibold text-blue-700">Важно: сервис не управляет вашими средствами и не совершает сделки за вас.</span>
            </p>
          </div>
        </div>
        
        {/* CTA */}
        <div className="text-center">
          <Button
            onClick={handleStart}
            className="px-8 py-4 text-lg"
          >
            Начать
            <ArrowRight className="w-5 h-5 ml-2" />
          </Button>
          
          <p className="mt-4 text-sm text-gray-500">
            Без регистрации • MVP версия
          </p>
        </div>
      </div>
      
      {/* Footer */}
      <footer className="text-center py-6 text-gray-500 text-sm">
        <p>
          ⚠️ Это информационный сервис, а не финансовый совет.
          <br />
          Инвестиции в криптовалюты связаны с высоким риском.
        </p>
      </footer>
    </div>
  )
}
