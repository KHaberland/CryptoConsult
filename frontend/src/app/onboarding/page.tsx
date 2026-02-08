'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useSessionStore } from '@/store/sessionStore'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { TrendingUp, Shield, Target, Ban } from 'lucide-react'

export default function OnboardingWelcomePage() {
  const router = useRouter()
  const { initSession, isReady, hasCompletedOnboarding } = useSessionStore()

  useEffect(() => {
    initSession()
  }, [initSession])

  // Если onboarding уже пройден — переходим дальше
  useEffect(() => {
    if (isReady && hasCompletedOnboarding) {
      router.push('/questionnaire')
    }
  }, [isReady, hasCompletedOnboarding, router])

  const handleNext = () => {
    router.push('/onboarding/disclaimer')
  }

  if (!isReady) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-white">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-blue-50 p-4">
      <div className="max-w-2xl mx-auto pt-8 pb-16">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <div className="bg-primary-600 p-3 rounded-2xl">
              <TrendingUp className="w-10 h-10 text-white" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Добро пожаловать в Крипто-Консультант 👋
          </h1>
        </div>

        {/* Mission statement */}
        <Card className="mb-6 border-primary-200 bg-primary-50">
          <CardContent className="text-center py-6">
            <p className="text-lg text-primary-800">
              Мы помогаем сохранять капитал, управлять рисками и инвестировать в криптовалюты 
              дисциплинированно, без лишнего стресса и паники.
            </p>
          </CardContent>
        </Card>

        {/* Why it matters */}
        <Card className="mb-6 border-amber-200 bg-amber-50">
          <CardContent className="py-6">
            <h3 className="text-lg font-semibold text-amber-800 mb-2">
              Почему это важно:
            </h3>
            <p className="text-amber-700">
              Большинство инвесторов теряют деньги из-за отсутствия плана и дисциплины. 
              Мы помогаем вам действовать системно и принимать взвешенные решения, даже при волатильном рынке.
            </p>
          </CardContent>
        </Card>

        {/* How we help */}
        <Card className="mb-8">
          <CardContent>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Как Крипто-Консультант помогает:
            </h3>
            
            <div className="space-y-4">
              <div className="flex items-start">
                <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center mr-3 flex-shrink-0 mt-0.5">
                  <span className="text-green-600 font-bold">✓</span>
                </div>
                <div>
                  <span className="text-gray-900 font-medium">Формирует сбалансированный портфель</span>
                  <span className="text-gray-600"> — распределяет инвестиции между крупными и перспективными криптовалютами, снижая риски.</span>
                </div>
              </div>
              
              <div className="flex items-start">
                <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center mr-3 flex-shrink-0 mt-0.5">
                  <span className="text-green-600 font-bold">✓</span>
                </div>
                <div>
                  <span className="text-gray-900 font-medium">Поддерживает долгосрочную стратегию</span>
                  <span className="text-gray-600"> — помогает не реагировать на краткосрочные колебания цен и придерживаться плана.</span>
                </div>
              </div>
              
              <div className="flex items-start">
                <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center mr-3 flex-shrink-0 mt-0.5">
                  <span className="text-green-600 font-bold">✓</span>
                </div>
                <div>
                  <span className="text-gray-900 font-medium">Контроль рисков и дисциплина</span>
                  <span className="text-gray-600"> — показывает ключевые показатели, предупреждает о значимых изменениях, помогает следовать выбранному плану.</span>
                </div>
              </div>
              
              <div className="flex items-start bg-blue-50 -mx-4 px-4 py-3 rounded-lg border border-blue-200">
                <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center mr-3 flex-shrink-0 mt-0.5">
                  <span className="text-blue-600 font-bold">✓</span>
                </div>
                <div>
                  <span className="text-blue-800 font-medium">Вы остаётесь хозяином своих средств</span>
                  <span className="text-blue-700"> — сервис не управляет деньгами и не совершает сделки за вас.</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Button with Slogan */}
        <div className="text-center">
          <Button 
            onClick={handleNext} 
            size="lg"
            className="px-12"
          >
            <Shield className="w-5 h-5 mr-2" />
            Следуйте выбранной стратегии
          </Button>
        </div>
      </div>
    </main>
  )
}
