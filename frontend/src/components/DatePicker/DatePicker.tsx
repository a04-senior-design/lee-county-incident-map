import dayjs from 'dayjs'
import { DatePickerInput } from '@mantine/dates'

type DateRange = [string | null, string | null]
type DatePickerProps = {
  dateRange: DateRange
  setDateRange: (value: DateRange) => void
}
function DatePicker({dateRange, setDateRange}: DatePickerProps) {
  const today = dayjs()
  const handleChange = (value: DateRange) => {
    setDateRange(value)
  }
  return (
    <DatePickerInput
      clearable
      type='range'
      value={dateRange}
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
