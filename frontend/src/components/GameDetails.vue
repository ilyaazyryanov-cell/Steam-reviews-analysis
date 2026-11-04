<script setup>
import { ref, onMounted, watch } from 'vue'

const props = defineProps(['game', 'compareIds'])
const emit = defineEmits(['go-back', 'toggle-compare', 'select-game'])

const API_URL = 'https://steam-analysis.ru/api'
const aspects = ref([])
const daysFilter = ref(null)
const excludeNeutralDetails = ref(false)
const sortBy = ref('mentions')
const sortDesc = ref(true)

const similarGames = ref([])

async function fetchSimilar() {
  const response = await fetch(`${API_URL}/games/${props.game.id}/similar?limit=8`)
  if (response.ok) {
    similarGames.value = await response.json()
  }
}

async function loadDetails() {
  let url = `${API_URL}/games/${props.game.id}/aspects?sort_by=${sortBy.value}&descending=${sortDesc.value}&exclude_neutral=${excludeNeutralDetails.value}`
  if (daysFilter.value) url += `&days=${daysFilter.value}`
  aspects.value = await fetch(url).then(r => r.json())
}

function toggleDaysFilter() {
  daysFilter.value = daysFilter.value === 90 ? null : 90
  loadDetails()
  fetchSimilar()
}

onMounted(loadDetails)
watch([sortBy, sortDesc, excludeNeutralDetails], loadDetails)
fetchSimilar()
</script>

<template>
  <div class="view-details">
    <button @click="emit('go-back')" class="btn-back-modern">
      <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"></path></svg>
      Back to list
    </button>
    
    <div class="details-header">
      <img :src="game.header_image" alt="cover" class="details-cover"/>
      <div class="details-title">
        <h2>{{ game.name }}</h2>
        <div class="details-actions">
          <label class="compare-checkbox details-compare">
            <input type="checkbox" :checked="compareIds.has(game.id)" @change="emit('toggle-compare', game.id)" />
            Add to compare
          </label>
          <button @click="toggleDaysFilter" class="btn-toggle" :class="{ active: daysFilter }">
            {{ daysFilter ? 'Showing last 90 days ✖' : 'Filter: Last 90 days' }}
          </button>
        </div>
      </div>
    </div>

    <div class="local-controls">
      <label class="control-label">
        <input type="checkbox" v-model="excludeNeutralDetails" /> Exclude Neutral
      </label>
      <label class="control-label">
        Sort by:
        <select v-model="sortBy" class="filter-select">
          <option value="mentions">Mentions</option>
          <option value="positive">Positive %</option>
          <option value="negative">Negative %</option>
          <option value="neutral">Neutral %</option>
          <option value="aspect">Aspect Name</option>
        </select>
      </label>
      <label class="control-label">
        <input type="checkbox" v-model="sortDesc" /> Descending
      </label>
    </div>

    <div class="table-responsive">
      <table class="aspects-table">
        <thead>
          <tr>
            <th>Aspect</th>
            <th>Mentions</th>
            <th>Positive</th>
            <th>Negative</th>
            <th>Neutral</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in aspects" :key="item.aspect">
            <td><strong>{{ item.aspect }}</strong></td>
            <td>{{ item.mentions }}</td>
            <td v-if="item.positive_percent !== null" class="pos">{{ item.positive_percent }}%</td>
            <td v-if="item.negative_percent !== null" class="neg">{{ item.negative_percent }}%</td>
            <td v-if="item.neutral_percent !== null">{{ item.neutral_percent }}%</td>
            <td v-if="item.positive_percent === null" colspan="3" class="no-data">— insufficient data (< 0.5%) —</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="similar-section" v-if="similarGames.length > 0">
  <h3>You might also like</h3>
  <div class="similar-grid">
    <div v-for="sim in similarGames" :key="sim.id" class="similar-card" @click="emit('select-game', sim)">
      <img :src="sim.header_image" :alt="sim.name" />
      <div class="similar-info">
        <span class="sim-name">{{ sim.name }}</span>
        <span class="sim-badge"> {{ sim.shared_aspects_count }} shared strengths</span>
      </div>
    </div>
  </div>
</div>
  </div>
</template>

<style scoped>
.details-header { display: flex; gap: 20px; margin-bottom: 20px; background: var(--surface); padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.details-cover { width: 300px; max-width: 100%; border-radius: 8px; object-fit: cover; }
.details-title { display: flex; flex-direction: column; justify-content: center; }
.details-title h2 { margin: 0 0 15px 0; font-size: 26px; }
.details-actions { display: flex; flex-direction: column; gap: 12px; align-items: flex-start; }
.details-compare { font-size: 15px; font-weight: bold; color: var(--primary); }

.local-controls { display: flex; gap: 20px; align-items: center; background: var(--surface); padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); flex-wrap: wrap; }
.control-label { display: flex; align-items: center; gap: 8px; font-weight: bold; font-size: 14px; cursor: pointer; }
.filter-select { padding: 6px; border: 1px solid var(--border); border-radius: 4px; }

.btn-toggle { background: #9ca3af; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; transition: 0.2s; }
.btn-toggle.active { background: #10b981; }

.pos { color: var(--pos); font-weight: bold;}
.neg { color: var(--neg); font-weight: bold;}
.no-data { color: #9ca3af; font-style: italic; text-align: center; }

@media (max-width: 768px) {
  .details-header { flex-direction: column; text-align: center; align-items: center; }
  .details-cover { width: 100%; max-width: 320px; }
  .details-actions { align-items: center; width: 100%; }
  .local-controls { flex-direction: column; align-items: stretch; gap: 12px; }
  .control-label { justify-content: space-between; }
  .filter-select { flex-grow: 1; max-width: 160px; }
}

.similar-section { margin-top: 40px; border-top: 1px solid var(--border); padding-top: 20px; }
.similar-section h3 { margin-bottom: 15px; color: var(--text); font-size: 18px; }
.similar-grid { 
  display: grid; 
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); 
  gap: 15px; 
}
.similar-card { 
  background: var(--surface); 
  border-radius: 8px; 
  cursor: pointer; 
  border: 1px solid var(--border); 
  transition: 0.2s; 
  display: flex;
  flex-direction: column;
  overflow: hidden; 
}
.similar-card:hover { 
  transform: translateY(-3px); 
  border-color: var(--primary); 
  box-shadow: 0 4px 12px rgba(0,0,0,0.1); 
}
.similar-card img { 
  width: 100%; 
  height: 90px; 
  object-fit: cover; 
  display: block;
}
.similar-info { 
  padding: 10px; 
  display: flex; 
  flex-direction: column; 
  align-items: flex-start;
  gap: 6px; 
  overflow: hidden;
}
.sim-name { 
  font-weight: 600; 
  font-size: 13px; 
  width: 100%;
  white-space: nowrap; 
  overflow: hidden; 
  text-overflow: ellipsis;
  line-height: 1.2;
}
.sim-badge { 
  font-size: 11px; 
  color: #10b981; 
  font-weight: 600; 
  background: #ecfdf5; 
  padding: 3px 6px; 
  border-radius: 4px; 
  white-space: nowrap;
}
</style>