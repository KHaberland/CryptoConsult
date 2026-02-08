'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useSessionStore } from '@/store/sessionStore'
import { usePortfolioStore } from '@/store/portfolioStore'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Alert } from '@/components/ui/Alert'
import { Progress } from '@/components/ui/Progress'
import { Slider } from '@/components/ui/Slider'
import { Input } from '@/components/ui/Input'
import { CheckCircle, TrendingUp } from 'lucide-react'

// Динамические AI-комментарии для горизонта инвестирования
const getHorizonComment = (years: number): string => {
  switch (years) {
    case 1:
      return '1 год — минимальный срок для консервативного инвестирования. Высокий риск не увидеть прибыль из-за волатильности рынка. Рекомендуем увеличить горизонт.'
    case 2:
      return '2 года — короткий срок. Возможна значительная волатильность. Будьте готовы к временным просадкам, не паникуйте при падении.'
    case 3:
      return '3 года — хороший стартовый горизонт. Достаточно времени для восстановления после коррекций. Оптимально для начинающих инвесторов.'
    case 4:
      return '4 года — сбалансированный срок. Охватывает типичный рыночный цикл. Хорошие шансы на положительную доходность.'
    case 5:
      return '5 лет — отличный горизонт для долгосрочного инвестора. Высокая вероятность прибыли при соблюдении стратегии.'
    case 6:
      return '6 лет — надёжный долгосрочный горизонт. Позволяет пережить несколько рыночных циклов и усреднить волатильность.'
    case 7:
      return '7 лет — идеальный срок для максимальной доходности. Исторически криптовалюты показывали значительный рост на таком горизонте.'
    default:
      return 'Выберите срок инвестирования от 1 до 7 лет.'
  }
}

// Динамические AI-комментарии для суммы инвестирования
const getAmountComment = (amount: number): string => {
  if (amount < 3000) {
    return `$${amount.toLocaleString()} — минимальная сумма для старта. Этого достаточно для знакомства с рынком и отработки стратегии, но диверсификация будет ограничена.`
  } else if (amount < 10000) {
    return `$${amount.toLocaleString()} — хорошая сумма для начинающего инвестора. Позволяет создать диверсифицированный портфель из 4-5 активов и применять стратегию DCA.`
  } else {
    return `$${amount.toLocaleString()} — солидная сумма для серьёзного инвестирования. Отличные возможности для диверсификации, DCA и долгосрочного роста капитала.`
  }
}

const QUESTIONS = [
  {
    id: 'name',
    title: 'Ваше имя',
    question: 'Как вас зовут?',
    comment: 'Это имя будет использоваться для входа в систему',
    type: 'text',
    placeholder: 'Например: Андрей',
    default: '',
  },
  {
    id: 'investment_horizon',
    title: 'Горизонт инвестирования',
    question: 'На какой срок вы готовы инвестировать средства?',
    comment: '', // Динамический комментарий
    type: 'slider',
    min: 1,
    max: 7,
    suffix: ' лет',
    default: 3,
    dynamicComment: true,
  },
  {
    id: 'investment_amount',
    title: 'Сумма инвестирования',
    question: 'Какую сумму вы готовы инвестировать?',
    comment: 'Минимальная сумма рекомендуется для получения реального эффекта DCA и диверсификации',
    type: 'amount',
    min: 1000,
    max: 50000,
    default: 10000,
  },
  {
    id: 'max_drawdown',
    title: 'Комфортная просадка',
    question: 'Какой уровень краткосрочной просадки вы готовы терпеть, не нервничая?',
    comment: 'Сервис предупреждает, если просадка превышает допустимый уровень',
    type: 'slider',
    min: 5,
    max: 50,
    suffix: '%',
    default: 30,
  },
  {
    id: 'needs_liquidity',
    title: 'Ликвидность',
    question: 'Нужна ли вам возможность быстро вывести часть средств при внезапной необходимости?',
    comment: 'Высокая ликвидность позволяет быстро адаптироваться, но может снижать доходность',
    type: 'boolean',
    options: [
      { value: true, label: 'Да, хочу возможность частичного вывода' },
      { value: false, label: 'Нет, могу держать весь портфель без вывода' },
    ],
    default: false,
  },
  {
    id: 'experience_level',
    title: 'Опыт инвестирования',
    question: 'Как бы вы оценили свой опыт в криптоактивах?',
    comment: 'Опыт не обязателен, сервис работает для всех уровней',
    type: 'select',
    options: [
      { value: 'beginner', label: 'Новичок, раньше не инвестировал' },
      { value: 'some', label: 'Немного опыта, пару сделок' },
      { value: 'medium', label: 'Средний опыт, понимание рынка' },
      { value: 'advanced', label: 'Продвинутый, делал регулярные инвестиции' },
    ],
    default: 'beginner',
  },
  {
    id: 'use_dca',
    title: 'Стратегия входа (DCA)',
    question: 'Хотите ли вы распределить инвестиции на несколько частей?',
    comment: 'Вход частями снижает краткосрочный риск; вход всей суммой увеличивает вероятность просадки',
    type: 'boolean',
    options: [
      { value: true, label: 'Да, разделить на 3-6 частей (рекомендовано)' },
      { value: false, label: 'Нет, вложить всю сумму сразу' },
    ],
    default: true,
  },
  {
    id: 'dca_parts',
    title: 'Количество частей DCA',
    question: 'На сколько частей разделить инвестиции?',
    comment: 'Чем больше частей, тем более плавный вход, но дольше период инвестирования',
    type: 'slider',
    min: 3,
    max: 6,
    suffix: ' частей',
    default: 4,
    condition: (answers: any) => answers.use_dca === true,
  },
  {
    id: 'use_default_portfolio',
    title: 'Состав портфеля',
    question: 'Хотите использовать базовый портфель?',
    comment: 'Базовый портфель: BTC 50%, ETH 25%, BNB 7.5%, SOL 7.5%, USDT 10%',
    type: 'boolean',
    options: [
      { value: true, label: 'Да, использовать базовый портфель' },
      { value: false, label: 'Нет, хочу настроить самостоятельно' },
    ],
    default: true,
  },
]

export default function QuestionnairePage() {
  const router = useRouter()
  const { initSession, isReady, hasCompletedOnboarding, userName } = useSessionStore()
  const { createProfile, createPortfolio, hasProfile, fetchProfile, isLoading, error, clearError } = usePortfolioStore()
  
  const [currentStep, setCurrentStep] = useState(0)
  const [answers, setAnswers] = useState<Record<string, any>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  
  // Инициализация сессии
  useEffect(() => {
    initSession()
  }, [initSession])
  
  // Если onboarding не пройден — редирект на соответствующий экран
  useEffect(() => {
    if (isReady && !hasCompletedOnboarding) {
      if (userName) {
        // Есть имя, но onboarding не пройден — на welcome
        router.push('/onboarding/welcome')
      } else {
        // Нет имени — на login
        router.push('/login')
      }
    }
  }, [isReady, hasCompletedOnboarding, userName, router])
  
  // Инициализация дефолтных значений (только при первой загрузке)
  useEffect(() => {
    setAnswers(prev => {
      // Если уже есть значения, не перезаписываем полностью
      if (Object.keys(prev).length > 0) {
        // Только обновляем имя если оно пустое
        if (!prev.name && userName) {
          return { ...prev, name: userName }
        }
        return prev
      }
      
      // Первая инициализация
      const defaults: Record<string, any> = {}
      QUESTIONS.forEach((q) => {
        if (q.id === 'name' && userName) {
          defaults[q.id] = userName
        } else {
          defaults[q.id] = q.default
        }
      })
      return defaults
    })
  }, [userName])
  
  // Проверка профиля после инициализации сессии
  useEffect(() => {
    if (isReady && hasCompletedOnboarding) {
      fetchProfile()
    }
  }, [isReady, hasCompletedOnboarding, fetchProfile])
  
  // Если профиль уже есть — редирект на dashboard
  useEffect(() => {
    if (hasProfile) {
      router.push('/dashboard')
    }
  }, [hasProfile, router])
  
  // Фильтруем вопросы по условиям
  const visibleQuestions = QUESTIONS.filter(
    (q) => !q.condition || q.condition(answers)
  )
  
  const currentQuestion = visibleQuestions[currentStep]
  const progress = ((currentStep + 1) / visibleQuestions.length) * 100
  
  const handleAnswer = (value: any) => {
    setAnswers((prev) => ({
      ...prev,
      [currentQuestion.id]: value,
    }))
  }
  
  const handleNext = () => {
    // Валидация текущего шага для текстовых полей
    if (currentQuestion?.type === 'text') {
      const value = answers[currentQuestion.id]
      if (!value || !value.trim()) {
        return // Не переходим если поле пустое
      }
    }
    
    if (currentStep < visibleQuestions.length - 1) {
      setCurrentStep((prev) => prev + 1)
    }
  }
  
  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1)
    }
  }
  
  const handleSubmit = async () => {
    // Валидация имени
    if (!answers.name || !answers.name.trim()) {
      return
    }
    
    setIsSubmitting(true)
    clearError()
    
    try {
      // Создаём профиль инвестора
      await createProfile({
        name: answers.name.trim(),
        investment_horizon: answers.investment_horizon,
        investment_amount: answers.investment_amount,
        max_drawdown: answers.max_drawdown,
        needs_liquidity: answers.needs_liquidity,
        experience_level: answers.experience_level,
        use_dca: answers.use_dca,
        dca_parts: answers.use_dca ? answers.dca_parts : null,
        use_default_portfolio: answers.use_default_portfolio,
      })
      
      // Создаём портфель только если выбран базовый
      if (answers.use_default_portfolio) {
        await createPortfolio({
          name: 'Мой портфель',
          initial_amount: answers.investment_amount,
          target_years: answers.investment_horizon,
        })
        router.push('/dashboard')
      } else {
        // Пользователь хочет создать портфель сам — на страницу создания
        router.push('/portfolio/create')
      }
    } catch (err) {
      // Ошибка сохранена в store
    } finally {
      setIsSubmitting(false)
    }
  }
  
  if (!isReady || isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-white">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Загрузка...</p>
        </div>
      </div>
    )
  }
  
  const isLastStep = currentStep === visibleQuestions.length - 1
  
  // Проверка валидности текущего шага для текстовых полей
  const isCurrentStepValid = currentQuestion?.type === 'text' 
    ? Boolean(answers[currentQuestion.id]?.trim())
    : true
  
  return (
    <main className="min-h-screen bg-gradient-to-br from-primary-50 to-white p-4">
      <div className="max-w-2xl mx-auto pt-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-2">
            <TrendingUp className="w-10 h-10 text-primary-600 mr-2" />
            <h1 className="text-2xl font-bold text-primary-600">
              Крипто-Консультант
            </h1>
          </div>
          <p className="text-gray-600">Анкета инвестора</p>
        </div>
        
        {/* Progress */}
        <div className="mb-6">
          <div className="flex justify-between text-sm text-gray-600 mb-2">
            <span>Вопрос {currentStep + 1} из {visibleQuestions.length}</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <Progress value={progress} />
        </div>
        
        {error && (
          <Alert variant="error" className="mb-4">
            {error}
          </Alert>
        )}
        
        {/* Question Card */}
        <Card className="mb-6">
          <CardContent>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">
              {currentQuestion?.title}
            </h2>
            <p className="text-gray-700 mb-4">
              {currentQuestion?.question}
            </p>
            
            {/* Answer Input */}
            <div className="my-6">
              {currentQuestion?.type === 'text' && (
                <Input
                  type="text"
                  value={answers[currentQuestion.id] ?? currentQuestion.default}
                  onChange={(e) => handleAnswer(e.target.value)}
                  placeholder={currentQuestion.placeholder}
                  className="text-lg"
                  autoFocus
                />
              )}
              
              {currentQuestion?.type === 'slider' && (
                <Slider
                  value={answers[currentQuestion.id] ?? currentQuestion.default}
                  onChange={handleAnswer}
                  min={currentQuestion.min!}
                  max={currentQuestion.max!}
                  valueSuffix={currentQuestion.suffix}
                />
              )}
              
              {currentQuestion?.type === 'amount' && (
                <div className="space-y-4">
                  <Input
                    type="number"
                    value={answers[currentQuestion.id] ?? currentQuestion.default}
                    onChange={(e) => handleAnswer(Number(e.target.value))}
                    min={currentQuestion.min}
                    max={currentQuestion.max}
                  />
                  <Slider
                    value={answers[currentQuestion.id] ?? currentQuestion.default}
                    onChange={handleAnswer}
                    min={currentQuestion.min!}
                    max={currentQuestion.max!}
                    valuePrefix="$"
                    showValue={false}
                  />
                  <p className="text-center text-lg font-semibold text-primary-600">
                    ${(answers[currentQuestion.id] ?? currentQuestion.default).toLocaleString()}
                  </p>
                </div>
              )}
              
              {(currentQuestion?.type === 'boolean' || currentQuestion?.type === 'select') && (
                <div className="space-y-3">
                  {currentQuestion.options?.map((option) => (
                    <button
                      key={String(option.value)}
                      onClick={() => handleAnswer(option.value)}
                      className={`w-full p-4 rounded-lg border-2 text-left transition-all ${
                        answers[currentQuestion.id] === option.value
                          ? 'border-primary-600 bg-primary-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-center">
                        <div className={`w-5 h-5 rounded-full border-2 mr-3 flex items-center justify-center ${
                          answers[currentQuestion.id] === option.value
                            ? 'border-primary-600 bg-primary-600'
                            : 'border-gray-300'
                        }`}>
                          {answers[currentQuestion.id] === option.value && (
                            <CheckCircle className="w-4 h-4 text-white" />
                          )}
                        </div>
                        <span className="text-gray-800">{option.label}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
            
            {/* Comment */}
            <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-600">
              <strong>Комментарий:</strong> {
                currentQuestion?.id === 'investment_horizon'
                  ? getHorizonComment(answers.investment_horizon ?? currentQuestion.default)
                  : currentQuestion?.id === 'investment_amount'
                    ? getAmountComment(answers.investment_amount ?? currentQuestion.default)
                    : currentQuestion?.comment
              }
            </div>
          </CardContent>
        </Card>
        
        {/* Navigation */}
        <div className="flex justify-between">
          <Button
            variant="secondary"
            onClick={handlePrev}
            disabled={currentStep === 0}
          >
            Назад
          </Button>
          
          {isLastStep ? (
            <Button
              onClick={handleSubmit}
              isLoading={isSubmitting}
              disabled={!isCurrentStepValid}
            >
              Завершить
            </Button>
          ) : (
            <Button 
              onClick={handleNext}
              disabled={!isCurrentStepValid}
            >
              Далее
            </Button>
          )}
        </div>
      </div>
    </main>
  )
}
