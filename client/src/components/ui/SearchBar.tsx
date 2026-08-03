import './SearchBar.css'

type SearchBarProps = {
  value: string
  onChange: (value: string) => void
}

function SearchBar({ value, onChange }: SearchBarProps) {
  return (
    <input
      type="search"
      className="search-bar"
      placeholder="Search by name or symbol"
      aria-label="Search assets"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}

export default SearchBar
