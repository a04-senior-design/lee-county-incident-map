//'use client'

import React from 'react'
import { DateRange, DateRangePicker } from '@/components/DatePicker'

const DatePicker = () => {
  const [dateRange, setDateRange] = React.useState(undefined)
  const presets = [
    {
      label: 'Today',
      dateRange: {
        from: new Date(),
        to: new Date()
      }
    },
    {
      label: 'Last 7 days',
      dateRange: {
        from: new Date(new Date().setDate(new Date().getDate() - 7)),
        to: new Date()
      }
    },
    {
      label: 'Last 30 days',
      dateRange: {
        from: new Date(new Date().setDate(new Date().getDate() - 30)),
        to: new Date()
      }
    },
    {
      label: 'Last 3 months',
      dateRange: {
        from: new Date(new Date().setMonth(new Date().getMonth() - 3)),
        to: new Date()
      }
    },
    {
      label: 'Last 6 months',
      dateRange: {
        from: new Date(new Date().setMonth(new Date().getMonth() - 6)),
        to: new Date()
      }
    },
    {
      label: 'Month to date',
      dateRange: {
        from: new Date(new Date().setDate(1)),
        to: new Date()
      }
    },
    {
      label: 'Year to date',
      dateRange: {
        from: new Date(new Date().setFullYear(new Date().getFullYear(), 0, 1)),
        to: new Date()
      }
    }
  ]
  return (
    <div className='flex flex-col items-center gap-y-4'>
      <DateRangePicker
        presets={presets}
        value={dateRange}
        onChange={setDateRange}
        className='w-60'
      />

      <p className='flex items-center rounded-md bg-gray-100 p-2 text-sm text-gray-500 dark:bg-gray-800 dark:text-gray-300'>
        Selected Range:{' '}
        {dateRange
          ? `${dateRange.from?.toLocaleDateString()} – ${dateRange.to?.toLocaleDateString() ?? ''}`
          : 'None'}
      </p>
    </div>
  )
}
export default DatePicker