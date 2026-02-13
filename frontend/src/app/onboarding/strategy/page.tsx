'use client'

import { useRouter } from 'next/navigation'
import { useSessionStore } from '@/store/sessionStore'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { ArrowLeft, Building2, Compass, ClipboardList, Info, ChevronRight } from 'lucide-react'

const PRINCIPLES = [
  {
    num: '1',
    title: 'Основа — крупнейшие активы',
    text: 'Большая часть портфеля формируется из устойчивых криптовалют с высокой капитализацией. Это снижает общий риск.',
  },
  {
    num: '2',
    title: 'Ограниченная доля более рискованных проектов',
    text: 'Небольшая часть выделяется на перспективные активы с потенциалом роста, но без чрезмерной концентрации.',
  },
  {
    num: '3',
    title: 'Постепенный вход (DCA)',
    text: 'Инвестирование равными частями во времени снижает риск покупки на пике рынка.',
  },
  {
    num: '4',
    title: 'Диверсификация',
    text: 'Средства распределяются между несколькими активами, чтобы уменьшить влияние одного негативного события.',
  },
  {
    num: '5',
    title: 'План выхода',
    text: 'Заранее определяются условия частичной фиксации прибыли или реструктуризации портфеля.',
  },
  {
    num: '6',
    title: 'Эмоциональная дисциплина',
    text: 'Решения принимаются по стратегии, а не под влиянием новостей и паники.',
  },
]

const QUESTIONNAIRE_TOPICS = [
  'инвестиционный горизонт',
  'допустимый уровень просадки',
  'размер капитала',
  'отношение к риску',
]

export default function OnboardingStrategyPage() {
  const router = useRouter()
  const { setOnboardingCompleted } = useSessionStore()

  const handleReady = () => {
    setOnboardingCompleted(true)
    router.push('/questionnaire')
  }

  const handleBack = () => router.push('/onboarding/module')

  return (
    <main className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-blue-50 p-4">
      <div className="max-w-2xl mx-auto pt-8 pb-24">
        {/* Шаг 1. Регистрация на криптобирже */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 mb-4">
              <Building2 className="w-6 h-6 text-primary-600" />
              <h2 className="text-xl font-bold text-gray-900">Шаг 1. Регистрация на криптобирже</h2>
            </div>
            <p className="text-gray-600 mb-4">
              Чтобы инвестировать, сначала необходимо зарегистрироваться на одной из крупных криптобирж.
            </p>
            <div className="flex flex-wrap gap-2 mb-4">
              <a
                href="https://www.binance.com"
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1.5 bg-primary-100 text-primary-700 rounded-lg font-medium hover:bg-primary-200 transition-colors"
              >
                Binance
              </a>
              <a
                href="https://www.coinbase.com"
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1.5 bg-primary-100 text-primary-700 rounded-lg font-medium hover:bg-primary-200 transition-colors"
              >
                Coinbase
              </a>
              <a
                href="https://www.kraken.com"
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1.5 bg-primary-100 text-primary-700 rounded-lg font-medium hover:bg-primary-200 transition-colors"
              >
                Kraken
              </a>
              <a
                href="https://www.bybit.com"
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1.5 bg-primary-100 text-primary-700 rounded-lg font-medium hover:bg-primary-200 transition-colors"
              >
                Bybit
              </a>
            </div>
            <p className="text-gray-600 mb-3">
              Регистрация обычно занимает от нескольких минут до нескольких часов, иногда — до нескольких дней.
            </p>
            <div className="bg-amber-50 rounded-lg p-4 border border-amber-100">
              <p className="font-medium text-amber-800 mb-1">Почему?</p>
              <p className="text-amber-700 text-sm">
                Биржа обязана провести идентификацию личности (KYC). Это стандартная процедура: загрузка документа, 
                подтверждение личности и иногда адреса проживания. Без этого полноценная работа с платформой невозможна.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* На чём основан КриптоКонсультант */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 mb-4">
              <Compass className="w-6 h-6 text-primary-600" />
              <h2 className="text-xl font-bold text-gray-900">На чём основан КриптоКонсультант</h2>
            </div>
            <p className="text-gray-600 mb-4">
              Программа ориентирована на консервативное инвестирование. Её цель — не максимальный риск, 
              а разумный баланс между стабильностью и ростом.
            </p>
            <p className="font-medium text-gray-800 mb-3">Основные принципы стратегии:</p>
            <div className="space-y-3">
              {PRINCIPLES.map((p) => (
                <div key={p.num} className="flex gap-3">
                  <span className="flex-shrink-0 w-7 h-7 rounded-full bg-primary-100 text-primary-700 font-bold text-sm flex items-center justify-center">
                    {p.num}
                  </span>
                  <div>
                    <h3 className="font-semibold text-gray-900">{p.title}</h3>
                    <p className="text-gray-600 text-sm mt-0.5">{p.text}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Шаг 2. Заполнение анкеты */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 mb-4">
              <ClipboardList className="w-6 h-6 text-primary-600" />
              <h2 className="text-xl font-bold text-gray-900">Шаг 2. Заполнение анкеты</h2>
            </div>
            <p className="text-gray-600 mb-4">
              Чтобы подобрать структуру портфеля под ваши цели, необходимо ответить на несколько простых вопросов:
            </p>
            <ul className="space-y-2">
              {QUESTIONNAIRE_TOPICS.map((topic) => (
                <li key={topic} className="flex items-center gap-2 text-gray-700">
                  <ChevronRight className="w-4 h-4 text-primary-500 flex-shrink-0" />
                  {topic}
                </li>
              ))}
            </ul>
            <p className="text-gray-600 mt-4">
              На основе ваших ответов программа сформирует персональную структуру портфеля.
            </p>
          </CardContent>
        </Card>

        {/* Важно понимать */}
        <Card className="mb-8 border-amber-200 bg-amber-50/50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 mb-4">
              <Info className="w-6 h-6 text-amber-600" />
              <h2 className="text-xl font-bold text-gray-900">Важно понимать</h2>
            </div>
            <p className="text-gray-700 font-medium mb-3">Создаваемый портфель — виртуальный.</p>
            <p className="text-gray-600 mb-3">Он:</p>
            <ul className="space-y-1 text-gray-600 mb-4">
              <li>• повторяет структуру вашего реального распределения</li>
              <li>• помогает видеть баланс и стратегию</li>
              <li>• служит инструментом планирования</li>
            </ul>
            <p className="text-gray-600">
              Но он не связан с вашей биржей и никак не управляет реальными средствами.
            </p>
            <p className="text-gray-700 font-medium mt-3">
              Вы принимаете инвестиционные решения самостоятельно.
            </p>
          </CardContent>
        </Card>

        <div className="mb-8 flex justify-center">
          <Button onClick={handleReady} size="lg" className="w-full sm:w-auto">
            Готовы заполнить анкету?
            <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        </div>

        {/* Navigation */}
        <div className="flex gap-4">
          <Button variant="secondary" onClick={handleBack} className="flex items-center">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Назад
          </Button>
        </div>
      </div>
    </main>
  )
}
