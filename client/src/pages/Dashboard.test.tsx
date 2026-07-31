import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Dashboard from './Dashboard'
import { fetchPortfolioBreakdown } from '../api'

vi.mock('../api', () => ({
  fetchPortfolioBreakdown: vi.fn(),
}))

vi.mock('../components/PortfolioComposition', () => ({
  default: ({ data }: { data: { name: string; value: number }[] }) => (
    <div data-testid="portfolio-composition">{JSON.stringify(data)}</div>
  ),
}))

const mockedFetch = vi.mocked(fetchPortfolioBreakdown)
const user = { userId: 1, username: 'ada', firstName: 'Ada', lastName: 'Lovelace' }

beforeEach(() => {
  mockedFetch.mockReset()
})

describe('Dashboard', () => {
  it('shows a loading state before the portfolio resolves', () => {
    mockedFetch.mockReturnValue(new Promise(() => {}))
    render(<Dashboard user={user} />)
    expect(screen.getByText('Loading portfolio...')).toBeInTheDocument()
  })

  it('shows an empty state when the portfolio has no value', async () => {
    mockedFetch.mockResolvedValue({ cash: 0, stock: 0, crypto: 0, bond: 0 })
    render(<Dashboard user={user} />)
    expect(await screen.findByText('No holdings to display.')).toBeInTheDocument()
  })

  it('renders the composition chart once data resolves', async () => {
    mockedFetch.mockResolvedValue({ cash: 100, stock: 50, crypto: 0, bond: 0 })
    render(<Dashboard user={user} />)
    expect(await screen.findByTestId('portfolio-composition')).toBeInTheDocument()
  })

  it('shows the error message on failure', async () => {
    mockedFetch.mockRejectedValue(new Error('Failed to fetch portfolio breakdown'))
    render(<Dashboard user={user} />)
    expect(await screen.findByText('Failed to fetch portfolio breakdown')).toBeInTheDocument()
  })
})
