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

// Динамические комментарии для комфортной просадки (вопрос 4). Число просадки берётся со шкалы и подставляется в заголовок.
const getDrawdownComment = (percent: number): string => {
  const header = `Просадка ${percent}%`
  if (percent <= 15) {
    return `${header}\n\nТакой уровень просадки подходит для горизонта 1–2 года и считается рабочей нормой рынка.\nЭто оптимальный вариант для начинающих, потому что не ломает психологию и позволяет учиться без паники.\nИнвестор ещё не до конца понимает циклы рынка, поэтому здесь важнее сохранить капитал, чем гнаться за доходностью.\n\nРекомендации по портфелю:\n• Консервативный: BTC / ETH — базовый и самый логичный выбор\n• Сбалансированный: допустима небольшая доля сильных альтов (10–20%)\n• Агрессивный: не рекомендуется — такой портфель почти неизбежно уйдёт глубже в минус`
  }
  if (percent <= 30) {
    return `${header}\n\nЭтот диапазон оправдан при горизонте 3–5 лет, когда у рынка есть время пройти фазу коррекции и восстановления.\nПодходит опытным инвесторам, которые понимают, как формируются циклы, и не реагируют на шум новостей.\nЧеловек уже знает, что временная боль — часть стратегии, а не сигнал к бегству.\n\nРекомендации по портфелю:\n• Консервативный: возможен, но просадка чаще связана с неудачным входом\n• Сбалансированный: оптимальный вариант — BTC/ETH как ядро + отобранные альты\n• Агрессивный: допустим, если инвестор готов к высокой волатильности и пересмотру позиций`
  }
  return `${header}\n\nТакая просадка допустима только при горизонте 5–7 лет и осознанном принятии риска.\nПодходит только очень опытным инвесторам, которые уже переживали глубокие падения и знают, что рынок способен долго оставаться в минусе.\nЗдесь держит не вера в цену, а понимание структуры рынка, сценариев восстановления и заранее принятый план.\n\nРекомендации по портфелю:\n• Консервативный: крайне редко и только в фазе глобального медвежьего рынка\n• Сбалансированный: возможно, если доля альтов высокая и рынок в капитуляции\n• Агрессивный: норма — но цена за потенциальную доходность, которую выдерживают единицы`
}

// Динамические комментарии для ликвидности (вопрос про частичный вывод)
const getLiquidityComment = (needsLiquidity: boolean): string => {
  if (needsLiquidity) {
    return `«Да, хочу возможность частичного вывода»\n\nЭтот ответ означает, что инвестору важна гибкость, а не только доходность.\n\nКак это влияет на портфель:\n• основа — высоколиквидные активы (BTC, ETH)\n• минимальная доля низколиквидных альтов\n• никаких долгих локов, фарминга с периодом ожидания, экзотических сетей\n\nДля кого подходит:\n• начинающие инвесторы\n• люди с активной жизнью, бизнесом, семьёй\n• те, кто не готов продавать активы в минусе из-за срочной нужды\n\nПочему это важно:\nКогда деньги могут понадобиться внезапно, ликвидность — это психологическая страховка.\nБез неё инвестор чаще всего фиксирует убыток в самый неподходящий момент.`
  }
  return `«Нет, могу держать весь портфель без вывода»\n\nЭтот ответ говорит о готовности заморозить капитал ради потенциально большей доходности.\n\nКак это влияет на портфель:\n• можно увеличить долю альтов\n• допускаются менее ликвидные активы\n• возможны долгосрочные стратегии без доступа к средствам\n\nДля кого подходит:\n• опытные инвесторы\n• те, у кого есть финансовая подушка вне крипты\n• люди, понимающие циклы и готовые долго ждать\n\nПочему это работает:\nОтсутствие необходимости вывода позволяет не реагировать на краткосрочные движения рынка и даёт шанс досидеть до полного цикла, где и формируется основная прибыль.\n\nБольшинство людей переоценивают свою способность «держать без вывода». Поэтому для 70–80% инвесторов ответ «Да, хочу возможность частичного вывода» — более зрелый, а не более слабый.`
}

// Динамические комментарии для опыта инвестирования
const getExperienceComment = (level: string): string => {
  switch (level) {
    case 'beginner':
      return `Новичок, раньше не инвестировал\n\nВы ещё не сталкивались с резкими падениями и не знаете, как рынок ведёт себя в стрессовых фазах.\n\nНа что это влияет:\n• портфель будет более консервативным\n• просадки ограничены\n• акцент на сохранение капитала и обучение`
    case 'some':
      return `Немного опыта, пару сделок\n\nВы знакомы с рынком, но ещё не прожили полноценный рыночный цикл.\n\nНа что это влияет:\n• умеренный уровень риска\n• ограниченная доля волатильных активов\n• защита от перегрузки портфеля альтами`
    case 'medium':
      return `Средний опыт, понимание рынка\n\nВы понимаете цикличность рынка и знаете, что временные просадки — нормальная часть инвестирования.\n\nНа что это влияет:\n• больше свободы в выборе активов\n• допускается более высокая волатильность\n• портфель может быть сбалансированным`
    case 'advanced':
      return `Продвинутый, делал регулярные инвестиции\n\nВы осознанно принимаете риск и умеете придерживаться стратегии даже в сложных фазах рынка.\n\nНа что это влияет:\n• доступ к агрессивным портфелям\n• более глубокие допустимые просадки\n• долгосрочные стратегии без жёстких ограничений`
    default:
      return 'Опыт не обязателен, сервис работает для всех уровней.'
  }
}

// Динамические комментарии для стратегии входа (DCA)
const getDcaComment = (useDca: boolean): string => {
  if (useDca) {
    return `«Да, разделить на 3–6 частей (рекомендовано)»\n\nНе пытайтесь угадать дно. Лучше распределить риск во времени.\n\nПочему это важно для новичка:\n• средняя цена входа становится адекватнее\n• первая просадка не вызывает паники\n• появляется возможность докупать, а не сожалеть\n\nКак это видит опытный инвестор:\nРынок можно не угадать, но риск можно контролировать.`
  }
  return `«Нет, вложить всю сумму сразу»\n\nЧто это означает:\nВы делаете ставку на тайминг — а это самое сложное в крипте.\n\nЧто чаще всего происходит:\n• рынок откатывается на −10…−30%\n• инвестор психологически не готов\n• хорошие активы продаются в минусе\n\nКому это подходит:\n• опытным инвесторам\n• тем, кто понимает структуру рынка\n• тем, кто готов видеть просадку и не дергаться`
}

// Форматирование даты по-русски (например: 9 февр. 2025)
const formatDateRu = (d: Date): string => {
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
}

// График дат входов от базовой даты (сегодня)
const getDcaSchedule = (parts: number, baseDate: Date): string => {
  const addDays = (d: Date, n: number) => {
    const r = new Date(d)
    r.setDate(r.getDate() + n)
    return r
  }
  const todayStr = formatDateRu(baseDate)
  const lines: string[] = []
  if (parts === 3) {
    lines.push(`Вход 1 — сегодня (${todayStr})`)
    lines.push(`Вход 2 — через 7–10 дней (${formatDateRu(addDays(baseDate, 7))}–${formatDateRu(addDays(baseDate, 10))})`)
    lines.push(`Вход 3 — через 7–10 дней (${formatDateRu(addDays(baseDate, 14))}–${formatDateRu(addDays(baseDate, 20))})`)
  } else if (parts === 4) {
    lines.push(`Вход 1 — сегодня (${todayStr})`)
    for (let i = 1; i < 4; i++) {
      const d = addDays(baseDate, i * 7)
      lines.push(`Вход ${i + 1} — через 7 дней (${formatDateRu(d)})`)
    }
  } else if (parts === 5) {
    lines.push(`Вход 1 — сегодня (${todayStr})`)
    // Входы 2–5: интервал 7–14 дней между входами
    for (let i = 1; i < 5; i++) {
      const from = addDays(baseDate, 7 * i)
      const to = addDays(baseDate, 14 * i)
      lines.push(`Вход ${i + 1} — через 7–14 дней (${formatDateRu(from)}–${formatDateRu(to)})`)
    }
  } else if (parts === 6) {
    lines.push(`Вход 1 — сегодня (${todayStr})`)
    for (let i = 1; i < 6; i++) {
      const from = addDays(baseDate, 10 * i)
      const to = addDays(baseDate, 14 * i)
      lines.push(`Вход ${i + 1} — через 10–14 дней (${formatDateRu(from)}–${formatDateRu(to)})`)
    }
  }
  return lines.join('\n')
}

// График дат и сумм по входам (для новичка: сумма разбита на части)
const getDcaScheduleWithAmounts = (parts: number, amount: number, baseDate: Date): string => {
  const addDays = (d: Date, n: number) => {
    const r = new Date(d)
    r.setDate(r.getDate() + n)
    return r
  }
  const perPart = Math.round((amount / parts) * 100) / 100
  const lines: string[] = []
  const todayStr = formatDateRu(baseDate)
  lines.push(`Вход 1 — сегодня (${todayStr}) — $${perPart.toLocaleString()}`)
  if (parts === 3) {
    lines.push(`Вход 2 — через 7–10 дней (${formatDateRu(addDays(baseDate, 7))}–${formatDateRu(addDays(baseDate, 10))}) — $${perPart.toLocaleString()}`)
    lines.push(`Вход 3 — через 7–10 дней (${formatDateRu(addDays(baseDate, 14))}–${formatDateRu(addDays(baseDate, 20))}) — $${perPart.toLocaleString()}`)
  } else {
    for (let i = 1; i < parts; i++) {
      const d = addDays(baseDate, 7 * i)
      lines.push(`Вход ${i + 1} — ${formatDateRu(d)} — $${perPart.toLocaleString()}`)
    }
  }
  return lines.join('\n')
}

// Динамические комментарии для количества частей DCA (с графиком дат от текущей даты; при передаче amount — с разбивкой суммы)
const getDcaPartsComment = (parts: number, baseDate: Date = new Date(), amount?: number): string => {
  const schedule = getDcaSchedule(parts, baseDate)
  let scheduleBlock = schedule ? `\n\n📅 График дат входов (от ${formatDateRu(baseDate)}):\n${schedule}` : ''
  if (amount != null && amount > 0) {
    const amountBlock = `Сумма $${amount.toLocaleString()}: по $${(Math.round((amount / parts) * 100) / 100).toLocaleString()} на каждый из ${parts} входов.\n\n📅 Даты и суммы входов (от ${formatDateRu(baseDate)}):\n${getDcaScheduleWithAmounts(parts, amount, baseDate)}`
    scheduleBlock = `\n\n${amountBlock}`
  }
  switch (parts) {
    case 3:
      return `Разбивка на 3 входа\n\n👉 Как лучше входить:\nРаздели сумму на 3 равные части. Войди первой частью сразу, второй — через 7–10 дней, третьей — ещё через 7–10 дней.${scheduleBlock}\n\n👉 Комментарий от практика:\nЭто быстрый вход, но уже без попытки угадать идеальное дно.`
    case 4:
      return `Разбивка на 4 входа\n\n👉 Как лучше входить:\nРаздели сумму на 4 равные части. Входи первой частью сразу, затем каждые 7 дней.${scheduleBlock}\n\n👉 Комментарий от практика:\nХороший баланс между контролем риска и скоростью входа в рынок.`
    case 5:
      return `Разбивка на 5 входов\n\n👉 Как лучше входить:\nРаздели сумму на 5 равных частей. Первая — сразу, остальные с интервалом 7–14 дней или на заметных коррекциях.${scheduleBlock}\n\n👉 Комментарий от практика:\nПозволяет спокойно переживать откаты и не переживать из-за тайминга.`
    case 6:
      return `Разбивка на 6 входов\n\n👉 Как лучше входить:\nРаздели сумму на 6 равных частей. Входи постепенно: сразу, затем каждые 10–14 дней или при снижениях рынка.${scheduleBlock}\n\n👉 Комментарий от практика:\nМаксимально защитный вариант: меньше стресса, меньше риска, больше дисциплины.`
    default:
      return 'Выберите от 3 до 6 частей для распределения входа.'
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
    id: 'experience_level',
    title: 'Опыт инвестирования',
    question: 'Как бы вы оценили свой опыт в криптоактивах?',
    comment: '',
    type: 'select',
    options: [
      { value: 'beginner', label: 'Новичок, раньше не инвестировал' },
      { value: 'some', label: 'Немного опыта, пару сделок' },
      { value: 'medium', label: 'Средний опыт, понимание рынка' },
      { value: 'advanced', label: 'Продвинутый, делал регулярные инвестиции' },
    ],
    default: 'beginner',
    dynamicComment: true,
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
    subtitle: 'Краткосрочные падения — нормальная волатильность крипторынка. Ограничения убытков — это ориентир, а не гарантия. Не продавайте сразу весь портфель, действуйте постепенно и сохраняйте дисциплину. Помните: рынок часто возвращается, а главная цель — остаться в игре и учиться.',
    comment: '',
    type: 'slider',
    min: 5,
    max: 50,
    suffix: '%',
    default: 30,
    dynamicComment: true,
  },
  {
    id: 'needs_liquidity',
    title: 'Ликвидность',
    question: 'Нужна ли вам возможность быстро вывести часть средств при внезапной необходимости?',
    comment: '',
    type: 'boolean',
    options: [
      { value: true, label: 'Да, хочу возможность частичного вывода' },
      { value: false, label: 'Нет, могу держать весь портфель без вывода' },
    ],
    default: false,
    dynamicComment: true,
    condition: (answers: any) => answers.experience_level !== 'beginner',
  },
  {
    id: 'use_dca',
    title: 'Стратегия входа (DCA)',
    question: 'DCA (Dollar-Cost Averaging) — усреднение цены входа. Хотите ли вы распределить инвестиции на несколько частей?',
    comment: '',
    type: 'boolean',
    options: [
      { value: true, label: 'Да, разделить на 3-6 частей (рекомендовано)' },
      { value: false, label: 'Нет, вложить всю сумму сразу' },
    ],
    default: true,
    dynamicComment: true,
    condition: (answers: any) => answers.experience_level !== 'beginner',
  },
  {
    id: 'dca_parts',
    title: 'Количество частей DCA',
    question: 'На сколько частей разделить инвестиции?',
    comment: '',
    type: 'slider',
    min: 3,
    max: 6,
    suffix: ' частей',
    default: 4,
    condition: (answers: any) => answers.use_dca === true,
    dynamicComment: true,
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
      // Ограничения для новичка: ликвидность да, DCA да, 3 части; лимиты по горизонту, сумме, просадке
      if (defaults.experience_level === 'beginner') {
        defaults.needs_liquidity = true
        defaults.use_dca = true
        defaults.dca_parts = 3
        defaults.investment_horizon = Math.min(defaults.investment_horizon ?? 3, 3)
        defaults.investment_amount = Math.min(defaults.investment_amount ?? 10000, 5000)
        defaults.max_drawdown = Math.min(defaults.max_drawdown ?? 30, 10)
      }
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
  
  const isBeginner = answers.experience_level === 'beginner'

  const handleAnswer = (value: any) => {
    setAnswers((prev) => {
      const isBeginnerPrev = prev.experience_level === 'beginner'
      let val = value
      if (currentQuestion?.id === 'investment_horizon' && isBeginnerPrev && value > 3) val = 3
      if (currentQuestion?.id === 'investment_amount' && isBeginnerPrev && value > 5000) val = 5000
      if (currentQuestion?.id === 'max_drawdown' && isBeginnerPrev && value > 10) val = 10
      const next = { ...prev, [currentQuestion.id]: val }
      if (currentQuestion?.id === 'experience_level' && val === 'beginner') {
        next.needs_liquidity = true
        next.use_dca = true
        next.dca_parts = 3
        if (prev.investment_horizon != null && prev.investment_horizon > 3) next.investment_horizon = 3
        if (prev.investment_amount != null && prev.investment_amount > 5000) next.investment_amount = 5000
        if (prev.max_drawdown != null && prev.max_drawdown > 10) next.max_drawdown = 10
      }
      return next
    })
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
      const isBeginnerSubmit = answers.experience_level === 'beginner'
      await createProfile({
        name: answers.name.trim(),
        investment_horizon: isBeginnerSubmit ? Math.min(answers.investment_horizon ?? 3, 3) : answers.investment_horizon,
        investment_amount: isBeginnerSubmit ? Math.min(answers.investment_amount ?? 5000, 5000) : answers.investment_amount,
        max_drawdown: isBeginnerSubmit ? Math.min(answers.max_drawdown ?? 10, 10) : answers.max_drawdown,
        needs_liquidity: isBeginnerSubmit ? true : answers.needs_liquidity,
        experience_level: answers.experience_level,
        use_dca: isBeginnerSubmit ? true : answers.use_dca,
        dca_parts: isBeginnerSubmit ? 3 : (answers.use_dca ? answers.dca_parts : null),
        use_default_portfolio: answers.use_default_portfolio,
      })
      
      // Создаём портфель только если выбран базовый
      if (answers.use_default_portfolio) {
        await createPortfolio({
          name: 'Мой портфель',
          initial_amount: answers.investment_amount,
          target_years: answers.investment_horizon,
          experience_level: answers.experience_level,
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
            {currentQuestion?.subtitle && (
              <p className="text-xs text-gray-500 mb-4">
                {currentQuestion.subtitle}
              </p>
            )}
            
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
              
              {currentQuestion?.type === 'slider' && !(currentQuestion?.id === 'dca_parts' && isBeginner) && (
                <Slider
                  value={
                    currentQuestion?.id === 'investment_horizon' && isBeginner
                      ? Math.min(answers[currentQuestion.id] ?? currentQuestion.default, 3)
                      : currentQuestion?.id === 'investment_amount' && isBeginner
                        ? Math.min(answers[currentQuestion.id] ?? currentQuestion.default, 5000)
                        : currentQuestion?.id === 'max_drawdown' && isBeginner
                          ? Math.min(answers[currentQuestion.id] ?? currentQuestion.default, 10)
                          : answers[currentQuestion.id] ?? currentQuestion.default
                  }
                  onChange={handleAnswer}
                  min={currentQuestion.min!}
                  max={
                    currentQuestion?.id === 'investment_horizon' && isBeginner
                      ? 3
                      : currentQuestion?.id === 'investment_amount' && isBeginner
                        ? 5000
                        : currentQuestion?.id === 'max_drawdown' && isBeginner
                          ? 10
                          : currentQuestion.max!
                  }
                  valueSuffix={currentQuestion.suffix}
                />
              )}
              {currentQuestion?.type === 'slider' && currentQuestion?.id === 'dca_parts' && isBeginner && (
                <p className="text-lg text-gray-700 py-2">
                  3 части (рекомендация для новичков)
                </p>
              )}
              
              {currentQuestion?.type === 'amount' && (
                <div className="space-y-4">
                  <Input
                    type="number"
                    value={answers[currentQuestion.id] ?? currentQuestion.default}
                    onChange={(e) => handleAnswer(Number(e.target.value))}
                    min={currentQuestion.min}
                    max={isBeginner ? 5000 : currentQuestion.max}
                  />
                  <Slider
                    value={Math.min(answers[currentQuestion.id] ?? currentQuestion.default, isBeginner ? 5000 : currentQuestion.max!)}
                    onChange={handleAnswer}
                    min={currentQuestion.min!}
                    max={isBeginner ? 5000 : currentQuestion.max!}
                    valuePrefix="$"
                    showValue={false}
                  />
                  <p className="text-center text-lg font-semibold text-primary-600">
                    ${(Math.min(answers[currentQuestion.id] ?? currentQuestion.default, isBeginner ? 5000 : currentQuestion.max!)).toLocaleString()}
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
            <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-600 whitespace-pre-line">
              <strong>Комментарий:</strong>{' '}
              {currentQuestion?.id === 'investment_horizon'
                ? getHorizonComment(answers.investment_horizon ?? currentQuestion.default)
                : currentQuestion?.id === 'investment_amount'
                  ? getAmountComment(answers.investment_amount ?? currentQuestion.default)
                  : currentQuestion?.id === 'max_drawdown'
                    ? getDrawdownComment(answers.max_drawdown ?? currentQuestion.default)
                    : currentQuestion?.id === 'needs_liquidity'
                      ? getLiquidityComment(answers.needs_liquidity ?? currentQuestion.default)
                      : currentQuestion?.id === 'experience_level'
                        ? getExperienceComment(answers.experience_level ?? currentQuestion.default)
                        : currentQuestion?.id === 'use_dca'
                          ? getDcaComment(answers.use_dca ?? currentQuestion.default)
                          : currentQuestion?.id === 'dca_parts'
                            ? getDcaPartsComment(
                                isBeginner ? 3 : (answers.dca_parts ?? currentQuestion.default),
                                new Date(),
                                isBeginner ? (answers.investment_amount ?? 0) : undefined
                              )
                            : currentQuestion?.comment}
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
