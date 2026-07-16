<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budgetLabel') }}</h3>
        </div>
        <div class="budget-slider-row">
          <input
            type="range"
            min="0"
            max="50000"
            step="100"
            v-model.number="budget"
            @input="onBudgetChange"
            class="budget-slider"
          >
          <span class="budget-readout">{{ formatCurrency(budget, currentCurrency) }}</span>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendedItems') }}</h3>
        </div>

        <div v-if="recommendations.length === 0" class="no-recommendations">
          {{ t('restocking.noRecommendations') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.quantity') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineTotal') }}</th>
                <th>{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in recommendations" :key="item.item_sku">
                <td><strong>{{ item.item_sku }}</strong></td>
                <td>{{ item.item_name }}</td>
                <td>{{ item.quantity }}</td>
                <td>{{ formatCurrency(item.unit_cost, currentCurrency) }}</td>
                <td><strong>{{ formatCurrency(item.line_total, currentCurrency) }}</strong></td>
                <td>{{ item.lead_time_days }} {{ t('restocking.days') }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="summary-line">
          <div class="summary-item">
            <span class="summary-label">{{ t('restocking.totalCost') }}</span>
            <span class="summary-value">{{ formatCurrency(totalCost, currentCurrency) }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">{{ t('restocking.remainingBudget') }}</span>
            <span class="summary-value">{{ formatCurrency(remainingBudget, currentCurrency) }}</span>
          </div>
        </div>

        <div v-if="submitSuccess" class="success-banner">
          {{ t('restocking.orderSuccess') }}
        </div>

        <button
          class="btn-primary"
          :disabled="submitting || recommendations.length === 0"
          @click="placeOrder"
        >
          {{ submitting ? t('restocking.placingOrder') : t('restocking.placeOrder') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency } from '../utils/currency.js'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency } = useI18n()

    const budget = ref(10000)
    const loading = ref(true)
    const error = ref(null)
    const recommendations = ref([])
    const totalCost = ref(0)
    const remainingBudget = ref(0)
    const submitting = ref(false)
    const submitSuccess = ref(false)

    let debounceTimer = null

    const loadRecommendations = async () => {
      try {
        loading.value = true
        error.value = null
        const response = await api.getRestockRecommendations(budget.value)
        recommendations.value = response.recommendations
        totalCost.value = response.total_cost
        remainingBudget.value = response.remaining_budget
      } catch (err) {
        error.value = 'Failed to load restock recommendations: ' + err.message
      } finally {
        loading.value = false
      }
    }

    const onBudgetChange = () => {
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(() => {
        loadRecommendations()
      }, 200)
    }

    const placeOrder = async () => {
      if (recommendations.value.length === 0) return

      submitting.value = true
      try {
        await api.createRestockOrder({
          budget: budget.value,
          line_items: recommendations.value.map(r => ({
            item_sku: r.item_sku,
            quantity: r.quantity
          }))
        })
        submitSuccess.value = true
        setTimeout(() => {
          submitSuccess.value = false
        }, 4000)
        await loadRecommendations()
      } catch (err) {
        error.value = 'Failed to place restock order: ' + err.message
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadRecommendations)

    return {
      t,
      currentCurrency,
      formatCurrency,
      budget,
      loading,
      error,
      recommendations,
      totalCost,
      remainingBudget,
      submitting,
      submitSuccess,
      onBudgetChange,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-slider-row {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.budget-slider {
  flex: 1;
  -webkit-appearance: none;
  appearance: none;
  height: 6px;
  border-radius: 3px;
  background: #e2e8f0;
  outline: none;
  cursor: pointer;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #2563eb;
  border: 2px solid #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  cursor: pointer;
}

.budget-slider::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #2563eb;
  border: 2px solid #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  cursor: pointer;
}

.budget-slider::-moz-range-track {
  height: 6px;
  border-radius: 3px;
  background: #e2e8f0;
}

.budget-slider:focus::-webkit-slider-thumb {
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.15);
}

.budget-readout {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  min-width: 110px;
  text-align: right;
}

.no-recommendations {
  padding: 1.5rem;
  text-align: center;
  color: #64748b;
  font-size: 0.938rem;
  background: #f8fafc;
  border-radius: 8px;
}

.summary-line {
  display: flex;
  gap: 2.5rem;
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.summary-label {
  font-size: 0.813rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.summary-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
}

.success-banner {
  margin-top: 1.25rem;
  padding: 0.875rem 1rem;
  background: #d1fae5;
  color: #059669;
  border-radius: 8px;
  font-size: 0.938rem;
  font-weight: 500;
}

.btn-primary {
  margin-top: 1.25rem;
  background: #2563eb;
  color: #ffffff;
  border: none;
  border-radius: 8px;
  padding: 0.625rem 1.5rem;
  font-size: 0.938rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
