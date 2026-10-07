import dayjs from 'dayjs'
import { DatePickerInput } from '@mantine/dates'
import { useEffect, useState } from 'react'
type DateRange = [string | null, string | null]
type DatePickerProps = {
  dateRange: DateRange
  setDateRange: (value: DateRange) => void
}
function DatePicker({ dateRange, setDateRange }: DatePickerProps) {
  const today = dayjs()
   const [draft, setDraft] = useState<DateRange>(dateRange)
  // keep the draft in sync when the parent changes it (presets, reset, etc.)
  useEffect(() => {
    setDraft(dateRange)
  }, [dateRange])

  const handleChange = (value: DateRange) => {
    setDraft(value)
    const [start, end] = value
    // commit only a complete range, or a cleared one
    if ((start && end) || (!start && !end)) {
      setDateRange(value)
    }
  }
  return (
    <DatePickerInput
      popoverProps={{ zIndex: 2000 }}
      styles={{
        presetsList: {
          color: '#000'
        },
        calendarHeader: {
          color: '#000'
        },
        day: {
          color: '#000'
        }
      }}
      clearable
      type='range'
      value={draft}
      onChange={handleChange}
      presets={[
        {
          value: [
            today.subtract(2, 'day').format('YYYY-MM-DD'),
            today.format('YYYY-MM-DD')
          ],
          label: 'Last two days'
        },
        {
          value: [
            today.subtract(7, 'day').format('YYYY-MM-DD'),
            today.format('YYYY-MM-DD')
          ],
          label: 'Last 7 days'
        },
        {
          value: [
            today.startOf('month').format('YYYY-MM-DD'),
            today.format('YYYY-MM-DD')
          ],
          label: 'This month'
        },
        {
          value: [
            today.subtract(1, 'month').startOf('month').format('YYYY-MM-DD'),
            today.subtract(1, 'month').endOf('month').format('YYYY-MM-DD')
          ],
          label: 'Last month'
        },
        {
          value: [
            today.subtract(1, 'year').startOf('year').format('YYYY-MM-DD'),
            today.subtract(1, 'year').endOf('year').format('YYYY-MM-DD')
          ],
          label: 'Last year'
        }
      ]}
    />
  )
}
export default DatePicker
