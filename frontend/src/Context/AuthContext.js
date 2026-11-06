import {createContext, useContext } from 'react'


export const AuthContext = createContext(null)
export const useAuth = () => {
  const checkAuth = useContext(AuthContext)
  if (!checkAuth) throw new Error('useAuth must be used inside AuthProvider')
  return checkAuth
}