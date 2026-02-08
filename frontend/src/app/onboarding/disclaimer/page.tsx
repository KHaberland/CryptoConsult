'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Alert } from '@/components/ui/Alert'
import { 
  AlertTriangle, 
  ArrowLeft, 
  CheckCircle,
  XCircle 
} from 'lucide-react'

const DISCLAIMER_POINTS = [
  {
    id: 'own_decisions',
    text: 'Все решения принимаются самостоятельно',
  },
  {
    id: 'informational',
    text: 'Сервис носит информационно-аналитический и рекомендательный характер',
  },
  {
    id: 'not_advisor',
    text: 'Сервис не является инвестиционным советником, брокером или управляющим активами',
  },
  {
    id: 'no_access',
    text: 'Сервис не управляет средствами и не имеет доступа к кошелькам инвестора',
  },
  {
    id: 'no_guarantee',
    text: 'Прошлые результаты не гарантируют будущей доходности',
  },
]

export default function OnboardingDisclaimerPage() {
  const router = useRouter()
  const [checkedItems, setCheckedItems] = useState<Record<string, boolean>>({})
  const [showExitConfirm, setShowExitConfirm] = useState(false)

  const allChecked = DISCLAIMER_POINTS.every(point => checkedItems[point.id])

  const toggleItem = (id: string) => {
    setCheckedItems(prev => ({
      ...prev,
      [id]: !prev[id]
    }))
  }

  const handleAgree = () => {
    if (allChecked) {
      router.push('/onboarding/strategy')
    }
  }

  const handleDisagree = () => {
    setShowExitConfirm(true)
  }

  const handleExit = () => {
    // Очищаем localStorage и возвращаем на главную
    if (typeof window !== 'undefined') {
      localStorage.removeItem('session_id')
      localStorage.removeItem('onboarding_completed')
    }
    router.push('/')
  }

  const handleBack = () => {
    router.push('/onboarding')
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-red-50 via-white to-orange-50 p-4">
      <div className="max-w-2xl mx-auto pt-8 pb-16">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <div className="bg-amber-500 p-3 rounded-2xl">
              <AlertTriangle className="w-10 h-10 text-white" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-gray-900">
            Отказ от ответственности
          </h1>
          <p className="text-gray-600 mt-2">
            Disclaimer
          </p>
        </div>

        {/* Warning */}
        <Alert variant="warning" className="mb-6">
          <strong>Внимание!</strong> Инвестирование в криптовалюты связано с высоким 
          риском и может привести к частичной или полной потере средств.
        </Alert>

        {/* Confirmation Points */}
        <Card className="mb-6">
          <CardContent>
            <p className="text-gray-700 mb-4 font-medium">
              Используя Крипто-Консультант, инвестор подтверждает, что:
            </p>
            
            <div className="space-y-3">
              {DISCLAIMER_POINTS.map((point) => (
                <button
                  key={point.id}
                  onClick={() => toggleItem(point.id)}
                  className={`w-full p-4 rounded-lg border-2 text-left transition-all ${
                    checkedItems[point.id]
                      ? 'border-green-500 bg-green-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-start">
                    <div className={`w-6 h-6 rounded-full border-2 mr-3 flex items-center justify-center flex-shrink-0 mt-0.5 ${
                      checkedItems[point.id]
                        ? 'border-green-500 bg-green-500'
                        : 'border-gray-300'
                    }`}>
                      {checkedItems[point.id] && (
                        <CheckCircle className="w-4 h-4 text-white" />
                      )}
                    </div>
                    <span className={`${checkedItems[point.id] ? 'text-green-800' : 'text-gray-700'}`}>
                      {point.text}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Risk Warning */}
        <Card className="mb-6 bg-gray-50">
          <CardContent>
            <p className="text-gray-600 text-sm leading-relaxed">
              Рынок крипто-активов подвержен высокой волатильности, регуляторным 
              и технологическим рискам. Инвестор принимает на себя риск возможных 
              убытков, включая полную потерю капитала.
            </p>
            <p className="text-gray-600 text-sm leading-relaxed mt-3">
              Перед инвестированием рекомендуется оценить финансовые возможности 
              и при необходимости проконсультироваться с независимым специалистом.
            </p>
          </CardContent>
        </Card>

        {/* Progress indicator */}
        {!allChecked && (
          <p className="text-center text-gray-500 mb-6">
            Подтвердите все пункты для продолжения 
            ({Object.values(checkedItems).filter(Boolean).length} из {DISCLAIMER_POINTS.length})
          </p>
        )}

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
                  Без согласия с условиями использовать сервис невозможно. 
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
              disabled={!allChecked}
            >
              Согласен
            </Button>
          </div>
        </div>
      </div>
    </main>
  )
}
