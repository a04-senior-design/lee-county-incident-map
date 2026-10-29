import { useState } from 'react'
import Button from '@mui/material/Button'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import TextSnippetIcon from '@mui/icons-material/TextSnippet'
import { useAuth } from '../../../Context/AuthContext'
function ReportBtn({
  isLoading,
  setDrawArea,
  setAreaBounds,
  handleReport,
  reportLoading
}) {
  const { user } = useAuth()
  const [anchorEl, setAnchorEl] = useState(null)
  const [reportBtn, setReportBtn] = useState(false)
  const open = Boolean(anchorEl)
  const handleClick = (event) => {
    setAnchorEl(event.currentTarget)
  }
  const handleClose = () => {
    setAnchorEl(null)
  }

  return (
    <div>
      <Button
        aria-controls={open ? 'basic-menu' : undefined}
        aria-haspopup='true'
        aria-expanded={open ? 'true' : undefined}
        loading={reportLoading}
        loadingPosition='start'
        disabled={user && !isLoading ? false : true}
        variant={reportBtn ? 'contained' : 'text'}
        color={reportBtn ? 'info' : 'primary'}
        value='report'
        sx={[
          (theme) =>
            theme.applyStyles('dark', {
              color: 'rgba(255, 255, 255, 0.92)'
            }),
          { padding: '8px 20px' }
        ]}
        startIcon={<TextSnippetIcon />}
        onClick={handleClick}
      >
        User Reports
      </Button>
      <Menu
        id='basic-menu'
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        slotProps={{
          list: {
            'aria-labelledby': 'basic-button'
          }
        }}
      >
        <MenuItem
          onClick={(e) => {
            handleClose()
            setReportBtn(true)
            handleReport(false)
            setAreaBounds(null)
          }}
        >
          Lee-County area
        </MenuItem>
        <MenuItem
          onClick={() => {
            handleClose()
            setDrawArea(true)
          }}
        >
          Customize area
        </MenuItem>
      </Menu>
    </div>
  )
}

export default ReportBtn
