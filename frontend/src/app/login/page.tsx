'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/Alert'
import { profileApi } from '@/services/api'
import { useSessionStore } from '@/store/sessionStore'
import { TrendingUp, User, Loader2 } from 'lucide-react'
import { APP_VERSION } from '@/version'

export default function LoginPage() {
  const router = useRouter()
  const { setSessionFromLookup, startNewUserSession } = useSessionStore()
  
  const [name, setName] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!name.trim()) {
      setError('Пожалуйста, введите ваше имя')
      return
    }
    
    setIsLoading(true)
    setError(null)
    
    try {
      // Ищем профиль по имени
      const data = await profileApi.lookup(name.trim())
      
      // Профиль найден — сохраняем данные и переходим к приветствию
      setSessionFromLookup(data.session_id, data.name)
      
      // Передаём данные через query params (или можно через state)
      router.push(`/welcome?name=${encodeURIComponent(data.name)}`)
      
    } catch (err: any) {
      if (err.response?.status === 404) {
        // Профиль не найден — новый пользователь
        // Начинаем новую сессию с новым session_id
        startNewUserSession(name.trim())
        router.push('/onboarding/welcome')
      } else if (!err.response) {
        // Сеть недоступна — backend не запущен или не отвечает
        setError(
          'Сервер не отвечает. Подождите 1–2 минуты после первого запуска (установка зависимостей). ' +
          'При повторных запусках — 15–20 секунд. Затем обновите страницу.'
        )
      } else {
        setError('Ошибка при проверке. Попробуйте ещё раз.')
      }
    } finally {
      setIsLoading(false)
    }
  }
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-white flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-100 rounded-full mb-4">
            <TrendingUp className="w-8 h-8 text-primary-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">
            Крипто-Консультант
          </h1>
          <p className="text-gray-600 mt-2">
            Введите ваше имя для входа
          </p>
        </div>
        
        {/* Form */}
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <form onSubmit={handleSubmit}>
            {error && (
              <Alert variant="error" className="mb-4">
                {error}
              </Alert>
            )}
            
            <div className="mb-6">
              <label 
                htmlFor="name" 
                className="block text-sm font-medium text-gray-700 mb-2"
              >
                Ваше имя
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  id="name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Например: Андрей"
                  className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-lg"
                  autoFocus
                  disabled={isLoading}
                />
              </div>
              <p className="mt-2 text-xs text-gray-500">
                Если вы уже пользовались программой, введите то же имя
              </p>
            </div>
            
            <Button
              type="submit"
              className="w-full py-3 text-lg"
              disabled={isLoading || !name.trim()}
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  Проверяем...
                </>
              ) : (
                'Продолжить'
              )}
            </Button>
          </form>
        </div>
        
        <p className="text-center text-xs text-gray-500 mt-6">
          v{APP_VERSION} • без регистрации
        </p>
      </div>
    </div>
  )
}
