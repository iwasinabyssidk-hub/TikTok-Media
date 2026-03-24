import axios from 'axios'

const client = axios.create({
  baseURL: '/',
  timeout: 30000,
})

export default client
