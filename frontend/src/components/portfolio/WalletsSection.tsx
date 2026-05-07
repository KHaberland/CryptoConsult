'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { ArrowLeftRight, Plus, Wallet as WalletIcon } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/Alert'
import { WalletCard } from '@/components/portfolio/WalletCard'
import { WalletFormModal } from '@/components/portfolio/WalletFormModal'
import { TransferBetweenWalletsModal } from '@/components/portfolio/TransferBetweenWalletsModal'
import { AdjustHoldingModal } from '@/components/portfolio/AdjustHoldingModal'
import { useSessionStore } from '@/store/sessionStore'
import { usePortfolioStore } from '@/store/portfolioStore'
import type { Wallet, WalletHolding } from '@/services/api'

export function WalletsSection() {
  const { isReady } = useSessionStore()
  const {
    wallets,
    error,
    fetchWallets,
    createWallet,
    updateWallet,
    deleteWallet,
    transferBetweenWallets,
    adjustHolding,
    clearError,
  } = usePortfolioStore()

  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Wallet | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)
  const [transferOpen, setTransferOpen] = useState(false)
  const [adjustTarget, setAdjustTarget] = useState<{
    wallet: Wallet
    holding: WalletHolding
  } | null>(null)

  useEffect(() => {
    if (isReady) {
      fetchWallets()
    }
  }, [isReady, fetchWallets])

  const canTransfer = useMemo(() => wallets.length >= 2, [wallets.length])

  const handleAddClick = () => {
    setEditing(null)
    setLocalError(null)
    clearError()
    setFormOpen(true)
  }

  const handleEdit = (wallet: Wallet) => {
    setEditing(wallet)
    setLocalError(null)
    clearError()
    setFormOpen(true)
  }

  const handleDelete = async (wallet: Wallet) => {
    if (wallet.is_default) return
    const confirmed = window.confirm(
      `Удалить кошелёк "${wallet.name}"? Действие необратимо.`,
    )
    if (!confirmed) return

    setLocalError(null)
    setDeletingId(wallet.id)
    try {
      await deleteWallet(wallet.id)
    } catch {
      // Ошибка уже записана в store.error через formatApiError.
    } finally {
      setDeletingId(null)
    }
  }

  const handleTransferClick = () => {
    setLocalError(null)
    clearError()
    setTransferOpen(true)
  }

  const handleAdjustHolding = (wallet: Wallet, holding: WalletHolding) => {
    setLocalError(null)
    clearError()
    setAdjustTarget({ wallet, holding })
  }

  const sortedWallets = useMemo(() => {
    return [...wallets].sort((a, b) => {
      if (a.is_default !== b.is_default) {
        return a.is_default ? -1 : 1
      }
      return a.name.localeCompare(b.name)
    })
  }, [wallets])

  return (
    <Card className="mb-8">
      <CardHeader className="flex flex-row items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <WalletIcon className="w-5 h-5 text-primary-600" />
          <CardTitle>Мои кошельки</CardTitle>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleTransferClick}
            disabled={!canTransfer}
            title={
              canTransfer
                ? 'Перевод между кошельками'
                : 'Для перевода нужно минимум 2 кошелька'
            }
          >
            <ArrowLeftRight className="w-4 h-4 mr-1" />
            Перевести
          </Button>
          <Button variant="primary" size="sm" onClick={handleAddClick}>
            <Plus className="w-4 h-4 mr-1" />
            Добавить кошелёк
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {(localError || error) && (
          <Alert variant="error" className="mb-4">
            {localError || error}
          </Alert>
        )}

        {sortedWallets.length === 0 ? (
          <div className="text-sm text-gray-600 py-6 text-center border border-dashed border-gray-200 rounded-lg">
            Кошельков пока нет.
            <Link
              href="#"
              onClick={(e) => {
                e.preventDefault()
                handleAddClick()
              }}
              className="ml-1 text-primary-600 hover:underline"
            >
              Создать первый кошелёк
            </Link>
            .
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {sortedWallets.map((w) => (
              <WalletCard
                key={w.id}
                wallet={w}
                onEdit={handleEdit}
                onDelete={
                  deletingId === w.id ? undefined : handleDelete
                }
                onAdjustHolding={handleAdjustHolding}
              />
            ))}
          </div>
        )}
      </CardContent>

      <WalletFormModal
        isOpen={formOpen}
        onClose={() => setFormOpen(false)}
        wallet={editing}
        onCreate={createWallet}
        onUpdate={updateWallet}
      />

      <TransferBetweenWalletsModal
        isOpen={transferOpen}
        onClose={() => setTransferOpen(false)}
        onConfirm={transferBetweenWallets}
        wallets={sortedWallets}
      />

      <AdjustHoldingModal
        isOpen={adjustTarget !== null}
        onClose={() => setAdjustTarget(null)}
        onConfirm={adjustHolding}
        wallet={adjustTarget?.wallet ?? null}
        holding={adjustTarget?.holding ?? null}
      />
    </Card>
  )
}

export default WalletsSection
