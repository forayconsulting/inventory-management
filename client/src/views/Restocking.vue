<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <!-- Budget Slider -->
      <div class="card budget-card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budget') }}</h3>
          <div class="budget-display">
            {{ currencySymbol }}{{ budget.toLocaleString() }}
          </div>
        </div>
        <div class="budget-slider-container">
          <input
            type="range"
            class="budget-slider"
            :min="0"
            :max="maxBudget"
            :step="sliderStep"
            v-model.number="budget"
          />
          <div class="budget-range">
            <span>{{ currencySymbol }}0</span>
            <span>{{ currencySymbol }}{{ maxBudget.toLocaleString() }}</span>
          </div>
        </div>
      </div>

      <!-- Summary Stats -->
      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.totalCost') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ totalCost.toLocaleString() }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.remainingBudget') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ remainingBudget.toLocaleString() }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.itemsSelected') }}</div>
          <div class="stat-value">{{ recommendations.length }}</div>
        </div>
      </div>

      <!-- Recommendations Table -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }} ({{ recommendations.length }})</h3>
          <button
            class="place-order-btn"
            :disabled="recommendations.length === 0 || submitting"
            @click="placeOrder"
          >
            {{ submitting ? t('common.loading') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="successMessage" class="success-message">{{ successMessage }}</div>

        <div v-if="recommendations.length === 0" class="empty-state">
          {{ t('restocking.noRecommendations') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th>{{ t('restocking.table.priority') }}</th>
                <th>{{ t('restocking.table.quantity') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.totalCost') }}</th>
                <th>{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rec in recommendations" :key="rec.forecast_id">
                <td><strong>{{ rec.item_sku }}</strong></td>
                <td>{{ rec.item_name }}</td>
                <td>
                  <span :class="['badge', rec.trend]">
                    {{ t(`trends.${rec.trend}`) }}
                  </span>
                </td>
                <td>
                  <span :class="['badge', rec.priority]">
                    {{ t(`priority.${rec.priority}`) }}
                  </span>
                </td>
                <td>{{ rec.recommended_quantity.toLocaleString() }}</td>
                <td>{{ currencySymbol }}{{ rec.unit_cost.toLocaleString() }}</td>
                <td><strong>{{ currencySymbol }}{{ rec.total_cost.toLocaleString() }}</strong></td>
                <td>{{ rec.lead_time_days }} {{ t('restocking.days') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Submitted Restocking Orders -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.submittedOrders') }} ({{ submittedOrders.length }})</h3>
        </div>

        <div v-if="submittedOrders.length === 0" class="empty-state">
          {{ t('restocking.noSubmittedOrders') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.orderNumber') }}</th>
                <th>{{ t('restocking.orderDate') }}</th>
                <th>{{ t('restocking.expectedDelivery') }}</th>
                <th>{{ t('restocking.table.leadTime') }}</th>
                <th>{{ t('orders.table.items') }}</th>
                <th>{{ t('restocking.totalValue') }}</th>
                <th>{{ t('restocking.status') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="order in submittedOrders" :key="order.id">
                <td><strong>{{ order.order_number }}</strong></td>
                <td>{{ formatDate(order.order_date) }}</td>
                <td>{{ formatDate(order.expected_delivery) }}</td>
                <td>{{ order.lead_time_days }} {{ t('restocking.days') }}</td>
                <td>
                  <details class="items-details">
                    <summary class="items-summary">
                      {{ t('orders.itemsCount', { count: order.items.length }) }}
                    </summary>
                    <div class="items-dropdown">
                      <div v-for="(item, idx) in order.items" :key="idx" class="item-entry">
                        <span class="item-name">{{ item.name }}</span>
                        <span class="item-meta">{{ t('orders.quantity') }}: {{ item.quantity }} @ {{ currencySymbol }}{{ item.unit_price }}</span>
                      </div>
                    </div>
                  </details>
                </td>
                <td><strong>{{ currencySymbol }}{{ order.total_value.toLocaleString() }}</strong></td>
                <td>
                  <span :class="['badge', getOrderStatusClass(order.status)]">
                    {{ t(`status.${order.status.toLowerCase()}`) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch, computed } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency } = useI18n()
    const { selectedLocation, selectedCategory, getCurrentFilters } = useFilters()

    const currencySymbol = computed(() => {
      return currentCurrency.value === 'JPY' ? '¥' : '$'
    })

    const loading = ref(true)
    const error = ref(null)
    const submitting = ref(false)
    const successMessage = ref(null)
    const budget = ref(25000)
    const maxBudget = ref(100000)
    const recommendations = ref([])
    const totalCost = ref(0)
    const remainingBudget = ref(0)
    const submittedOrders = ref([])

    const sliderStep = computed(() => {
      if (maxBudget.value > 100000) return 1000
      if (maxBudget.value > 10000) return 500
      return 100
    })

    const loadRecommendations = async () => {
      try {
        loading.value = true
        error.value = null

        const data = await api.getRestockingRecommendations(budget.value)
        recommendations.value = data.recommendations
        totalCost.value = data.total_cost
        remainingBudget.value = data.remaining_budget
        maxBudget.value = Math.max(data.max_budget, budget.value)

        // Ensure budget doesn't exceed max on first load
        if (budget.value > maxBudget.value) {
          budget.value = maxBudget.value
        }
      } catch (err) {
        error.value = 'Failed to load restocking recommendations: ' + err.message
      } finally {
        loading.value = false
      }
    }

    const loadSubmittedOrders = async () => {
      try {
        submittedOrders.value = await api.getRestockingOrders()
      } catch (err) {
        console.error('Failed to load submitted orders:', err)
      }
    }

    // Debounce budget changes to avoid excessive API calls
    let budgetTimeout = null
    const debouncedLoadRecommendations = () => {
      if (budgetTimeout) clearTimeout(budgetTimeout)
      budgetTimeout = setTimeout(async () => {
        try {
          const data = await api.getRestockingRecommendations(budget.value)
          recommendations.value = data.recommendations
          totalCost.value = data.total_cost
          remainingBudget.value = data.remaining_budget
        } catch (err) {
          console.error('Failed to update recommendations:', err)
        }
      }, 200)
    }

    watch(budget, () => {
      debouncedLoadRecommendations()
    })

    // Watch for filter changes and reload
    watch([selectedLocation, selectedCategory], () => {
      loadRecommendations()
    })

    const placeOrder = async () => {
      if (recommendations.value.length === 0) return

      submitting.value = true
      successMessage.value = null

      try {
        const orderItems = recommendations.value.map(rec => ({
          item_sku: rec.item_sku,
          item_name: rec.item_name,
          quantity: rec.recommended_quantity,
          unit_cost: rec.unit_cost
        }))

        const newOrder = await api.submitRestockingOrder({
          items: orderItems,
          total_budget: budget.value
        })

        submittedOrders.value.unshift(newOrder)
        successMessage.value = t('restocking.orderPlaced')

        // Clear the success message after 5 seconds
        setTimeout(() => {
          successMessage.value = null
        }, 5000)
      } catch (err) {
        error.value = t('restocking.orderFailed') + ': ' + err.message
      } finally {
        submitting.value = false
      }
    }

    const formatDate = (dateString) => {
      const { currentLocale } = useI18n()
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return new Date(dateString).toLocaleDateString(locale, {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    }

    const getOrderStatusClass = (status) => {
      const statusMap = {
        'Delivered': 'success',
        'Shipped': 'info',
        'Processing': 'warning',
        'Backordered': 'danger'
      }
      return statusMap[status] || 'info'
    }

    onMounted(async () => {
      await Promise.all([loadRecommendations(), loadSubmittedOrders()])
    })

    return {
      t,
      loading,
      error,
      submitting,
      successMessage,
      budget,
      maxBudget,
      sliderStep,
      recommendations,
      totalCost,
      remainingBudget,
      submittedOrders,
      currencySymbol,
      placeOrder,
      formatDate,
      getOrderStatusClass
    }
  }
}
</script>

<style scoped>
.budget-card {
  margin-bottom: 1.5rem;
}

.budget-display {
  font-size: 1.5rem;
  font-weight: 700;
  color: #2563eb;
}

.budget-slider-container {
  padding: 0.5rem 0;
}

.budget-slider {
  width: 100%;
  height: 8px;
  -webkit-appearance: none;
  appearance: none;
  background: #e2e8f0;
  border-radius: 4px;
  outline: none;
  cursor: pointer;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #2563eb;
  cursor: pointer;
  border: 3px solid white;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.3);
  transition: box-shadow 0.2s;
}

.budget-slider::-webkit-slider-thumb:hover {
  box-shadow: 0 2px 10px rgba(37, 99, 235, 0.5);
}

.budget-slider::-moz-range-thumb {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #2563eb;
  cursor: pointer;
  border: 3px solid white;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.3);
}

.budget-range {
  display: flex;
  justify-content: space-between;
  margin-top: 0.5rem;
  font-size: 0.813rem;
  color: #64748b;
}

.place-order-btn {
  padding: 0.625rem 1.5rem;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
}

.place-order-btn:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.success-message {
  background: #d1fae5;
  border: 1px solid #6ee7b7;
  color: #065f46;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #64748b;
  font-size: 0.938rem;
}

/* Items details styling (matches Orders.vue) */
.items-details {
  position: relative;
}

.items-summary {
  cursor: pointer;
  color: #3b82f6;
  font-weight: 500;
  list-style: none;
  user-select: none;
  display: inline-block;
}

.items-summary::-webkit-details-marker {
  display: none;
}

.items-summary::before {
  content: '\25B6';
  display: inline-block;
  margin-right: 0.375rem;
  font-size: 0.75rem;
  transition: transform 0.2s;
}

.items-details[open] .items-summary::before {
  transform: rotate(90deg);
}

.items-summary:hover {
  color: #2563eb;
  text-decoration: underline;
}

.items-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 0.5rem;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  padding: 0.75rem;
  z-index: 10;
  min-width: 300px;
  max-width: 400px;
}

.item-entry {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.5rem;
  border-bottom: 1px solid #f1f5f9;
}

.item-entry:last-child {
  border-bottom: none;
}

.item-name {
  font-size: 0.875rem;
  font-weight: 500;
  color: #0f172a;
}

.item-meta {
  font-size: 0.813rem;
  color: #64748b;
}
</style>
