
import Snackbar from '@mui/material/Snackbar'
import Alert from '@mui/material/Alert'

function AppAlert({ AlertContent, SetAlertContent }) {
  const { vertical, horizontal, open, severity, content, key } = AlertContent
 

  const handleClose = () => {
    SetAlertContent({ ...AlertContent, open: false })
  }

  return (
    <div>
      <Snackbar
        anchorOrigin={{ vertical, horizontal }}
        open={open}
        autoHideDuration={5500}
        onClose={handleClose}
        message='Note archived'
        key={key}
      >
        <Alert severity={severity}>{content}</Alert>
      </Snackbar>
    </div>
  )
}

export default AppAlert
