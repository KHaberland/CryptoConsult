'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useSessionStore } from '@/store/sessionStore'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { TrendingUp, Sparkles, ArrowRight } from 'lucide-react'

export default function NewUserWelcomePage() {
  const router = useRouter()
  const { initSession, isReady, userName, hasCompletedOnboarding } = useSessionStore()

  useEffect(() => {
    initSession()
  }, [initSession])

  // Если нет имени — редирект на login
  useEffect(() => {
    if (isReady && !userName) {
      router.push('/login')
    }
  }, [isReady, userName, router])

  // Если onboarding уже пройден — на dashboard
  useEffect(() => {
    if (isReady && hasCompletedOnboarding) {
      router.push('/dashboard')
    }
  }, [isReady, hasCompletedOnboarding, router])

  const handleStart = () => {
    router.push('/onboarding')
  }

  if (!isReady || !userName) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-white">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-blue-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-primary-100 rounded-2xl mb-6">
            <TrendingUp className="w-10 h-10 text-primary-600" />
          </div>
        </div>
        
        {/* Welcome Card */}
        <Card className="text-center">
          <CardContent className="p-8">
            <div className="mb-6">
              <Sparkles className="w-12 h-12 text-yellow-500 mx-auto mb-4" />
              <h1 className="text-3xl font-bold text-gray-900 mb-2">
                Добро пожаловать, {userName}! 👋
              </h1>
            </div>
            
            <p className="text-lg text-gray-600 mb-2">
              Похоже, вы у нас впервые.
            </p>
            <p className="text-gray-600 mb-8">
              Давайте настроим ваш портфель!
            </p>
            
            <Button
              onClick={handleStart}
              className="w-full py-4 text-lg"
            >
              Начать настройку
              <ArrowRight className="w-5 h-5 ml-2" />
            </Button>
          </CardContent>
        </Card>
        
        <p className="text-center text-xs text-gray-500 mt-6">
          Это займёт около 2-3 минут
        </p>
      </div>
    </div>
  )
}
