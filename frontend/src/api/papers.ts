import request from './request'

export interface Paper {
  id: number
  title: string
  description?: string
  time_limit_seconds?: number
  items: Array<{ id: number; question_id: number; sort_order: number }>
  created_at: string
  updated_at: string
}

export interface PaperListResponse {
  items: Paper[]
  total: number
  page: number
  page_size: number
}

export const paperApi = {
  list(params?: { page?: number; page_size?: number; keyword?: string }) {
    return request.get<any, PaperListResponse>('/papers', { params })
  },

  get(id: number) {
    return request.get<any, Paper>(`/papers/${id}`)
  },

  create(data: {
    title: string
    description?: string
    time_limit_seconds?: number
    question_ids?: number[]
  }) {
    return request.post<any, Paper>('/papers', data)
  },

  update(id: number, data: Partial<Paper>) {
    return request.put<any, Paper>(`/papers/${id}`, data)
  },

  delete(id: number) {
    return request.delete(`/papers/${id}`)
  },

  addItem(paperId: number, questionId: number) {
    return request.post(`/papers/${paperId}/items`, null, { params: { question_id: questionId } })
  },

  removeItem(paperId: number, itemId: number) {
    return request.delete(`/papers/${paperId}/items/${itemId}`)
  }
}
