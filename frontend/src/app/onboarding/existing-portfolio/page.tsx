'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { useSessionStore } from '@/store/sessionStore'
import { Briefcase, Sparkles, ArrowLeft } from 'lucide-react'

/**
 * Шаг онбординга: вопрос о наличии существующего портфеля.
 * - Нет → стандартная анкета и создание портфеля «с нуля».
 * - Да  → анкета в режиме `mode=import` и страница импорта портфеля.
 */
export default function ExistingPortfolioQuestionPage() {
  const router = useRouter()
  const {
    initSession,
    isReady,
    userName,
    hasCompletedOnboarding,
    setHasExistingPortfolio,
  } = useSessionStore()

  useEffect(() => {
    initSession()
  }, [initSession])

  // Если пользователь не прошёл вводный onboarding — отправляем туда.
  useEffect(() => {
    if (!isReady) return
    if (!userName) {
      router.push('/login')
      return
    }
    if (!hasCompletedOnboarding) {
      router.push('/onboarding/welcome')
    }
  }, [isReady, userName, hasCompletedOnboarding, router])

  const handleAnswer = (hasExisting: boolean) => {
    setHasExistingPortfolio(hasExisting)
    if (hasExisting) {
      router.push('/questionnaire?mode=import')
    } else {
      router.push('/questionnaire')
    }
  }

  if (!isReady || !userName || !hasCompletedOnboarding) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-white">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-blue-50 p-4">
      <div className="max-w-2xl mx-auto pt-8 pb-24">
        <Card>
          <CardContent className="py-8 text-center">
            <h1 className="text-2xl font-bold text-gray-900 mb-4">
              У вас уже есть инвестиционный портфель?
            </h1>
            <p className="text-gray-600 mb-2">
              Например, на бирже или холодном кошельке.
            </p>
            <p className="text-gray-600 mb-8">
              Если да — мы импортируем его и продолжим работать с реальными активами.
              Если нет — поможем составить портфель с нуля по нашей методике.
            </p>

            <div className="grid md:grid-cols-2 gap-4">
              <Button
                onClick={() => handleAnswer(false)}
                variant="secondary"
                className="py-6 text-lg"
              >
                <Sparkles className="w-5 h-5 mr-2" />
                Нет, начать с нуля
              </Button>
              <Button
                onClick={() => handleAnswer(true)}
                className="py-6 text-lg"
              >
                <Briefcase className="w-5 h-5 mr-2" />
                Да, ввести существующий
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-start mt-6">
          <Button
            variant="secondary"
            onClick={() => router.push('/onboarding/strategy')}
            className="flex items-center"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Назад
          </Button>
        </div>
      </div>
    </main>
  )
}
