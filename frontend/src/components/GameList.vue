<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps(['compareIds'])
const emit = defineEmits(['toggle-compare', 'select-game'])

const API_URL = 'https://steam-analysis.ru/api'
const canonicalAspects = ref([])
const games = ref([])
const currentPage = ref(1)
const totalPages = ref(1)
const totalItems = ref(0)

const searchQuery = ref('')
const searchSuggestions = ref([])
const advancedFilters = ref([{ aspect: '', minPositive: null, maxNegative: null }])

const fetchAspects = async () => {
  canonicalAspects.value = await fetch(`${API_URL}/aspects`).then(r => r.json())
}

const addFilterRow = () => {
  advancedFilters.value.push({ aspect: '', minPositive: null, maxNegative: null })
}

function removeFilterRow(index) {
  advancedFilters.value.splice(index, 1)
  if (!advancedFilters.value.length) addFilterRow()
}

async function fetchSuggestions() {
  if (searchQuery.value.length < 3) {
    searchSuggestions.value = []
    return
  }
  const res = await fetch(`${API_URL}/games?search=${encodeURIComponent(searchQuery.value)}&page_size=5`).then(r => r.json())
  searchSuggestions.value = res.items || []
}

function selectSuggestion(game) {
  searchQuery.value = game.name
  searchSuggestions.value = []
  applyFilters()
}

async function fetchGames() {
  const payloadFilters = advancedFilters.value
    .filter(f => f.aspect !== '')
    .map(f => ({
      aspect: f.aspect,
      min_positive: f.minPositive !== null && f.minPositive !== '' ? Number(f.minPositive) : null,
      max_negative: f.maxNegative !== null && f.maxNegative !== '' ? Number(f.maxNegative) : null
    }))
  
  const res = await fetch(`${API_URL}/games/advanced_search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      search: searchQuery.value, filters: payloadFilters, page: currentPage.value, page_size: 12, exclude_neutral: false
    })
  }).then(r => r.json())
  
  games.value = res.items || []
  totalPages.value = res.pages || 1
  totalItems.value = res.total || 0
}

function applyFilters() {
  searchSuggestions.value = []
  currentPage.value = 1
  fetchGames()
}

function resetFilters() {
  searchQuery.value = ''
  searchSuggestions.value = []
  advancedFilters.value = [{ aspect: '', minPositive: null, maxNegative: null }]
  applyFilters()
}

function changePage(delta) {
  const newPage = currentPage.value + delta
  if (newPage >= 1 && newPage <= totalPages.value) {
    currentPage.value = newPage
    fetchGames()
  }
}

onMounted(() => {
  fetchAspects()
  fetchGames()
})
</script>

<template>
  <div class="view-list">
    <div class="filters-panel">
      <div class="search-wrapper">
        <input v-model="searchQuery" @input="fetchSuggestions" @keyup.enter="applyFilters" placeholder="Search for a game..." class="search-input" />
        <ul v-if="searchSuggestions.length > 0" class="suggestions-dropdown">
          <li v-for="s in searchSuggestions" :key="s.id" @click="selectSuggestion(s)">
            <img :src="s.header_image || 'https://via.placeholder.com/40x20'" alt="cover" class="suggestion-img" />
            <span>{{ s.name }}</span>
          </li>
        </ul>
      </div>
      
      <div v-for="(filter, index) in advancedFilters" :key="index" class="filter-row">
        <select v-model="filter.aspect" class="filter-select">
          <option value="">Select aspect...</option>
          <option v-for="asp in canonicalAspects" :key="asp" :value="asp">{{ asp }}</option>
        </select>
        <input v-model.number="filter.minPositive" type="number" placeholder="Min Positive %" class="filter-number" min="0" max="100"/>
        <input v-model.number="filter.maxNegative" type="number" placeholder="Max Negative %" class="filter-number" min="0" max="100"/>
        <button @click="removeFilterRow(index)" class="btn-remove">✖</button>
      </div>

      <div class="filter-actions">
        <button @click="addFilterRow" class="btn-secondary">+ Add Aspect</button>
        <button @click="resetFilters" class="btn-secondary btn-reset">Reset</button>
        <button @click="applyFilters" class="btn-primary">Search</button>
      </div>
    </div>

    <p class="results-count">Games found: {{ totalItems }}</p>

    <div class="games-grid">
      <div v-for="game in games" :key="game.id" class="game-card">
        <img :src="game.header_image || 'https://via.placeholder.com/300x140?text=No+Image'" alt="cover" class="game-cover" @click="emit('select-game', game)" />
        <div class="game-info">
          <h3 @click="emit('select-game', game)">{{ game.name }}</h3>
          <label class="compare-checkbox">
            <input type="checkbox" :checked="compareIds.has(game.id)" @change="emit('toggle-compare', game.id)" />
            Add to compare
          </label>
        </div>
      </div>
    </div>

    <div class="pagination" v-if="totalPages > 1">
      <button @click="changePage(-1)" :disabled="currentPage === 1">◀ Prev</button>
      <span>Page {{ currentPage }} of {{ totalPages }}</span>
      <button @click="changePage(1)" :disabled="currentPage === totalPages">Next ▶</button>
    </div>
  </div>
</template>

<style scoped>
.filters-panel { background: var(--surface); padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; }
.search-wrapper { position: relative; margin-bottom: 15px; }
.search-input { width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: 6px; font-size: 16px; box-sizing: border-box; }
.suggestions-dropdown { position: absolute; top: 100%; left: 0; right: 0; background: white; border: 1px solid var(--border); border-radius: 4px; margin: 0; padding: 0; list-style: none; max-height: 250px; overflow-y: auto; z-index: 50; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
.suggestions-dropdown li { display: flex; align-items: center; padding: 10px; border-bottom: 1px solid var(--border); cursor: pointer; }
.suggestion-img { width: 40px; height: 20px; object-fit: cover; margin-right: 10px; border-radius: 2px; }

.filter-row { display: flex; gap: 10px; align-items: center; margin-bottom: 10px; }
.filter-select { flex-grow: 1; padding: 10px; border: 1px solid var(--border); border-radius: 6px; }
.filter-number { width: 150px; padding: 10px; border: 1px solid var(--border); border-radius: 6px; }
.btn-remove { background: #fee2e2; color: #ef4444; border: none; border-radius: 6px; cursor: pointer; padding: 0 15px; font-weight: bold; height: 40px; }

.filter-actions { display: flex; gap: 10px; margin-top: 15px; flex-wrap: wrap; }
.btn-primary { background: var(--primary); color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; margin-left: auto; }
.btn-secondary { background: #9ca3af; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; }

.games-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 20px; }
.game-card { background: var(--surface); border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); transition: transform 0.2s; }
.game-card:hover { transform: translateY(-3px); }
.game-cover { width: 100%; height: 140px; object-fit: cover; cursor: pointer; }
.game-info { padding: 15px; }
.game-info h3 { 
  margin: 0 0 10px 0; 
  font-size: 16px; 
  cursor: pointer; 
  color: var(--primary); 
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.3;
  min-height: 2.6em;
}
.compare-checkbox { font-size: 14px; color: #4b5563; cursor: pointer; display: flex; align-items: center; gap: 5px; }
.results-count { font-weight: 600; color: #6b7280; margin-bottom: 15px; }

.pagination { display: flex; justify-content: center; align-items: center; gap: 20px; margin-top: 30px; }
.pagination button { padding: 8px 16px; border: 1px solid var(--border); background: var(--surface); border-radius: 6px; cursor: pointer; font-weight: 600; }
.pagination button:disabled { opacity: 0.5; cursor: not-allowed; }

@media (max-width: 768px) {
  .games-grid { grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; }
  .filter-row { flex-direction: column; align-items: stretch; }
  .filter-number, .btn-remove { width: 100%; box-sizing: border-box; }
  .filter-actions { flex-direction: column; }
  .btn-primary, .btn-reset { margin-left: 0; width: 100%; }
}
</style>