import { useState, useEffect, useRef, ChangeEvent } from 'react'
import { ActionIcon } from '@mantine/core'
import { TimeInput } from '@mantine/dates'
import AccessTimeIcon from '@mui/icons-material/AccessTime'

interface Props {
  label: string
  timeRange: string
  setTimeRange: React.Dispatch<React.SetStateAction<string[]>>
  index: number
}

function TimePicker({ label,timeRange, setTimeRange, index }: Props) {
  const [time, setTime] = useState<string>('')
  const ref = useRef<HTMLInputElement>(null)
  //   useEffect(() => {
  //     console.log('time here', time)
  //   }, [time])
  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    const newValue = event.target.value
    setTime(newValue)
    setTimeRange((prev) => {
      const updated = [...prev]
      updated[index] = newValue
      return updated
    })
  }
  //   useEffect(() => {
  //     console.log('time after change: ', timeRange)
  //   }, [timeRange])
  const pickerControl = (
    <ActionIcon
      variant='subtle'
      color='gray'
      onClick={() => ref.current?.showPicker()}
    >
      <AccessTimeIcon />
    </ActionIcon>
  )

  return (
    <TimeInput
      label={label}
      ref={ref}
      value={timeRange}
      rightSection={pickerControl}
      onChange={handleChange}
    />
  )
}

export default TimePicker
