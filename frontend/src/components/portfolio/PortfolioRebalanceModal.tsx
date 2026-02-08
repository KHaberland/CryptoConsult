'use client'

import { useState } from 'react'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/Alert'
import { CheckCircle, ArrowRight, Loader2 } from 'lucide-react'

export interface PortfolioAsset {
  symbol: string
  name: string
  percentage: number
}

interface PortfolioRebalanceModalProps {
  isOpen: boolean
  onClose: () => void
  currentAssets: PortfolioAsset[]
  newAssets: PortfolioAsset[]
  onConfirm: () => Promise<void>
}

export function PortfolioRebalanceModal({
  isOpen,
  onClose,
  currentAssets,
  newAssets,
  onConfirm,
}: PortfolioRebalanceModalProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [showSuccess, setShowSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleConfirm = async () => {
    console.log('handleConfirm called, newAssets:', newAssets)
    setIsLoading(true)
    setError(null)
    
    try {
      await onConfirm()
      console.log('onConfirm success, showing success screen')
      setShowSuccess(true)
    } catch (err: any) {
      console.error('onConfirm error:', err)
      setError(err.message || 'Ошибка при обновлении портфеля')
    } finally {
      setIsLoading(false)
    }
  }

  const handleClose = () => {
    setShowSuccess(false)
    setError(null)
    onClose()
  }

  // Экран успеха
  if (showSuccess) {
    return (
      <Modal
        isOpen={isOpen}
        onClose={handleClose}
        size="lg"
        showCloseButton={false}
        closeOnOverlayClick={false}
      >
        <div className="text-center py-6">
          <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
            <CheckCircle className="w-10 h-10 text-green-600" />
          </div>
          
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            Поздравляем!
          </h2>
          <p className="text-gray-600 mb-6">
            Вы успешно изменили свой портфель
          </p>
          
          <div className="bg-gray-50 rounded-lg p-4 mb-6">
            <h3 className="text-sm font-medium text-gray-700 mb-3">
              Новый портфель выглядит так:
            </h3>
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs text-gray-500 border-b">
                  <th className="pb-2">Актив</th>
                  <th className="pb-2 text-right">Доля</th>
                </tr>
              </thead>
              <tbody>
                {newAssets.map((asset) => (
                  <tr key={asset.symbol} className="border-b last:border-0">
                    <td className="py-2">
                      <div className="flex items-center">
                        <div className="w-6 h-6 bg-primary-100 rounded-full flex items-center justify-center mr-2">
                          <span className="text-xs font-bold text-primary-600">
                            {asset.symbol.slice(0, 2)}
                          </span>
                        </div>
                        <div>
                          <span className="font-medium text-gray-900">{asset.symbol}</span>
                          <span className="text-xs text-gray-500 ml-1">{asset.name}</span>
                        </div>
                      </div>
                    </td>
                    <td className="py-2 text-right">
                      <span className="font-semibold text-green-600">
                        {asset.percentage}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          <Button onClick={handleClose} className="w-full">
            Отлично!
          </Button>
        </div>
      </Modal>
    )
  }

  // Экран подтверждения
  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Изменение портфеля"
      size="xl"
      closeOnOverlayClick={false}
    >
      <div>
        <p className="text-gray-600 mb-4">
          Вы хотите переформатировать свой портфель?
        </p>

        {error && (
          <Alert variant="error" className="mb-4">
            {error}
          </Alert>
        )}

        {/* Сравнение портфелей */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Текущий портфель */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-500 mb-3">
              Текущий портфель
            </h3>
            <table className="w-full">
              <tbody>
                {currentAssets.map((asset) => (
                  <tr key={asset.symbol} className="border-b last:border-0">
                    <td className="py-2">
                      <div className="flex items-center">
                        <div className="w-6 h-6 bg-gray-200 rounded-full flex items-center justify-center mr-2">
                          <span className="text-xs font-bold text-gray-600">
                            {asset.symbol.slice(0, 2)}
                          </span>
                        </div>
                        <span className="text-sm text-gray-700">{asset.symbol}</span>
                      </div>
                    </td>
                    <td className="py-2 text-right text-sm text-gray-600">
                      {asset.percentage}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>


          {/* Новый портфель */}
          <div className="bg-primary-50 rounded-lg p-4 border-2 border-primary-200">
            <h3 className="text-sm font-medium text-primary-700 mb-3">
              Новый портфель
            </h3>
            <table className="w-full">
              <tbody>
                {newAssets.map((asset) => {
                  const currentAsset = currentAssets.find(a => a.symbol === asset.symbol)
                  const diff = currentAsset 
                    ? asset.percentage - currentAsset.percentage 
                    : asset.percentage
                  const isNew = !currentAsset
                  const isRemoved = false // Для удалённых нужна отдельная логика

                  return (
                    <tr key={asset.symbol} className="border-b border-primary-100 last:border-0">
                      <td className="py-2">
                        <div className="flex items-center">
                          <div className="w-6 h-6 bg-primary-200 rounded-full flex items-center justify-center mr-2">
                            <span className="text-xs font-bold text-primary-700">
                              {asset.symbol.slice(0, 2)}
                            </span>
                          </div>
                          <span className="text-sm font-medium text-gray-900">
                            {asset.symbol}
                          </span>
                          {isNew && (
                            <span className="ml-1 text-xs bg-green-100 text-green-700 px-1 rounded">
                              новый
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-2 text-right">
                        <span className="text-sm font-semibold text-primary-700">
                          {asset.percentage}%
                        </span>
                        {diff !== 0 && !isNew && (
                          <span className={`ml-1 text-xs ${diff > 0 ? 'text-green-600' : 'text-red-600'}`}>
                            ({diff > 0 ? '+' : ''}{diff.toFixed(1)}%)
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        <ModalFooter>
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={isLoading}
          >
            Нет
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={isLoading || newAssets.length === 0}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Сохраняем...
              </>
            ) : (
              'Да, изменить'
            )}
          </Button>
        </ModalFooter>
        
        {newAssets.length === 0 && (
          <p className="text-red-500 text-sm mt-2">
            Ошибка: список новых активов пуст
          </p>
        )}
      </div>
    </Modal>
  )
}
