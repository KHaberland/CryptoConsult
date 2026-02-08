'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useSessionStore } from '@/store/sessionStore'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { 
  ArrowLeft, 
  Target, 
  Wallet, 
  PieChart, 
  Shuffle, 
  Calendar, 
  Eye, 
  Diamond, 
  LogOut,
  TrendingUp,
  XCircle
} from 'lucide-react'

const STRATEGY_STEPS = [
  {
    icon: Target,
    title: 'Цели и горизонты',
    description: 'На какой срок вы планируете инвестировать и какой уровень просадки готовы выдержать?',
    color: 'bg-blue-100 text-blue-600',
  },
  {
    icon: Wallet,
    title: 'Ваш капитал',
    description: 'Сколько вы можете вложить безопасно, не затрагивая финансовую подушку?',
    color: 'bg-green-100 text-green-600',
  },
  {
    icon: PieChart,
    title: 'Портфель устойчивых активов',
    description: 'Основу портфеля составляют надёжные криптовалюты (например, Bitcoin), на которые может приходиться 50% и более. Небольшая часть выделяется на перспективные проекты с более высоким потенциалом роста.',
    color: 'bg-purple-100 text-purple-600',
  },
  {
    icon: Shuffle,
    title: 'Диверсификация и стабильность',
    description: 'Не концентрируйте всё в одном активе; часть средств можно держать в стейблкоинах для снижения волатильности.',
    color: 'bg-orange-100 text-orange-600',
  },
  {
    icon: Calendar,
    title: 'Регулярные инвестиции (DCA)',
    description: 'Вход в рынок осуществляется постепенно, равными долями, без попыток поймать краткосрочные пики и падения.',
    color: 'bg-teal-100 text-teal-600',
  },
  {
    icon: Eye,
    title: 'Следим, но без паники',
    description: 'Портфель пересматривается только при значимых рыночных или фундаментальных изменениях.',
    color: 'bg-indigo-100 text-indigo-600',
  },
  {
    icon: Diamond,
    title: 'Следуем плану',
    description: 'Дисциплина важнее хайпа — мы поможем придерживаться стратегии и не реагировать на шум.',
    color: 'bg-pink-100 text-pink-600',
  },
  {
    icon: LogOut,
    title: 'План выхода',
    description: 'Заранее определяем условия частичной продажи или ребалансировки, чтобы принимать решения спокойно и обдуманно.',
    color: 'bg-red-100 text-red-600',
  },
]

export default function OnboardingStrategyPage() {
  const router = useRouter()
  const { setOnboardingCompleted } = useSessionStore()
  const [showExitConfirm, setShowExitConfirm] = useState(false)

  const handleAgree = () => {
    // Сохраняем что onboarding пройден
    setOnboardingCompleted(true)
    router.push('/questionnaire')
  }

  const handleDisagree = () => {
    setShowExitConfirm(true)
  }

  const handleExit = () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('session_id')
      localStorage.removeItem('onboarding_completed')
    }
    router.push('/')
  }

  const handleBack = () => {
    router.push('/onboarding/disclaimer')
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-blue-50 p-4">
      <div className="max-w-3xl mx-auto pt-8 pb-16">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <div className="bg-primary-600 p-3 rounded-2xl">
              <TrendingUp className="w-10 h-10 text-white" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">
            Инвестируйте с умом и дисциплиной
          </h1>
        </div>

        {/* Introduction */}
        <div className="text-center mb-6">
          <p className="text-gray-600">
            Чтобы составить стратегию под вас, ответьте на несколько вопросов. 
            Мы будем сопровождать вас на каждом шаге:
          </p>
        </div>

        {/* Strategy Steps */}
        <div className="grid gap-4 mb-8">
          {STRATEGY_STEPS.map((step, index) => {
            const Icon = step.icon
            return (
              <Card key={index} className="hover:shadow-md transition-shadow">
                <CardContent className="py-4">
                  <div className="flex items-start">
                    <div className={`p-2 rounded-lg mr-4 ${step.color}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center mb-1">
                        <span className="text-sm font-bold text-gray-400 mr-2">
                          {index + 1}.
                        </span>
                        <h3 className="font-semibold text-gray-900">
                          {step.title}
                        </h3>
                      </div>
                      <p className="text-gray-600 text-sm">
                        {step.description}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>

        {/* Call to Action */}
        <Card className="mb-8 border-green-200 bg-green-50">
          <CardContent className="text-center">
            <p className="text-green-800 font-medium">
              Если вы согласны следовать консервативной стратегии инвестирования, 
              необходимо заполнить анкету.
            </p>
          </CardContent>
        </Card>

        {/* Exit Confirmation Modal */}
        {showExitConfirm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <Card className="max-w-md w-full">
              <CardContent className="text-center">
                <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
                <h3 className="text-xl font-bold text-gray-900 mb-2">
                  Вы уверены?
                </h3>
                <p className="text-gray-600 mb-6">
                  Сервис работает только с консервативной стратегией инвестирования. 
                  Вы будете перенаправлены на главную страницу.
                </p>
                <div className="flex gap-3">
                  <Button 
                    variant="secondary" 
                    className="flex-1"
                    onClick={() => setShowExitConfirm(false)}
                  >
                    Остаться
                  </Button>
                  <Button 
                    variant="danger" 
                    className="flex-1"
                    onClick={handleExit}
                  >
                    Выйти
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="flex gap-4">
          <Button 
            variant="secondary" 
            onClick={handleBack}
            className="flex items-center"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Назад
          </Button>
          
          <div className="flex-1 flex gap-3">
            <Button 
              variant="outline"
              className="flex-1 border-red-300 text-red-600 hover:bg-red-50"
              onClick={handleDisagree}
            >
              Не согласен
            </Button>
            <Button 
              className="flex-1"
              onClick={handleAgree}
            >
              Согласен, заполнить анкету
            </Button>
          </div>
        </div>
      </div>
    </main>
  )
}
