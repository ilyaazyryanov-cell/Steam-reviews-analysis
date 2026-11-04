<script setup>
import { ref, computed, watch, onMounted } from 'vue'

const props = defineProps(['compareIds'])
const emit = defineEmits(['go-back', 'clear-compare'])

const API_URL = 'https://steam-analysis.ru/api'
const compareData = ref([])
const compareExcludeNeutral = ref(false)

async function loadCompareView() {
  if (props.compareIds.size === 0) return
  const params = new URLSearchParams()
  props.compareIds.forEach(id => params.append('app_ids', id))
  params.append('exclude_neutral', compareExcludeNeutral.value)
  
  compareData.value = await fetch(`${API_URL}/games/compare?${params}`).then(r => r.json())
}

const allComparedAspects = computed(() => {
  const aspSet = new Set()
  compareData.value.forEach(game => {
    Object.keys(game.aspects).forEach(a => {
      if (game.aspects[a].mentions !== null && game.aspects[a].mentions >= 5) aspSet.add(a)
    })
  })
  return Array.from(aspSet).sort()
})

function getBestGameForAspect(aspect) {
  let bestId = null
  let maxPos = -1
  compareData.value.forEach(game => {
    const stats = game.aspects[aspect]
    if (stats && stats.positive_percent !== null && stats.positive_percent > maxPos) {
      maxPos = stats.positive_percent
      bestId = game.id
    }
  })
  return bestId
}

onMounted(loadCompareView)
watch(compareExcludeNeutral, loadCompareView)
</script>

<template>
  <div class="view-compare">
    <div class="compare-actions">
      <button @click="emit('go-back')" class="btn-back-modern">
        <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"></path></svg>
        Back to list
      </button>
      
      <button @click="emit('clear-compare')" class="btn-clear-modern">
        Clear All
      </button>
    </div>
    
    <div class="compare-header">
      <h2>Game Comparison</h2>
      <label class="control-label">
        <input type="checkbox" v-model="compareExcludeNeutral" /> Exclude Neutral Reviews
      </label>
    </div>
    
    <div class="table-responsive">
      <table class="aspects-table compare-table">
        <thead>
          <tr>
            <th class="aspect-col">Aspect</th>
            <th v-for="game in compareData" :key="game.id" class="game-col">
              <div class="game-title">{{ game.name }}</div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="aspect in allComparedAspects" :key="aspect">
            <td class="aspect-name"><strong>{{ aspect }}</strong></td>
            <td v-for="game in compareData" :key="game.id" class="stat-cell">
              <div v-if="game.aspects[aspect] && game.aspects[aspect].positive_percent !== null" 
                   class="stat-box" 
                   :class="{'is-winner': getBestGameForAspect(aspect) === game.id}">
                <div class="stat-row pos">
                  <span class="value">{{ game.aspects[aspect].positive_percent }}%</span>
                </div>
                <div class="stat-row neg">
                  <span class="value">{{ game.aspects[aspect].negative_percent }}%</span>
                </div>
              </div>
              <div v-else class="no-data">—</div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.compare-header { display: flex; justify-content: space-between; align-items: center; background: var(--surface); padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); flex-wrap: wrap; gap: 15px; }
.compare-header h2 { margin: 0; color: var(--primary); }
.control-label { display: flex; align-items: center; gap: 8px; font-weight: bold; font-size: 14px; cursor: pointer; }

.compare-table { border-collapse: separate; border-spacing: 0; min-width: 700px; }
.aspect-col { width: 200px; background: #f9fafb; position: sticky; left: 0; z-index: 2; border-right: 2px solid var(--border); }
.game-col { text-align: center; background: #f9fafb; border-bottom: 2px solid var(--border) !important; }
.game-title { font-size: 16px; font-weight: 700; color: var(--text); padding: 10px 0; }

.aspect-name { position: sticky; left: 0; background: var(--surface); z-index: 1; border-right: 2px solid var(--border) !important; }
.stat-cell { text-align: center; vertical-align: middle; padding: 10px !important; }

.stat-box { display: inline-flex; flex-direction: column; gap: 6px; padding: 12px; border-radius: 8px; background: #f9fafb; border: 1px solid var(--border); position: relative; min-width: 100px; }
.stat-box.is-winner { background: #f0fdf4; border-color: #86efac; box-shadow: 0 2px 4px rgba(16, 185, 129, 0.1); }
.winner-badge { position: absolute; top: -10px; left: 50%; transform: translateX(-50%); background: #10b981; color: white; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 12px; text-transform: uppercase; letter-spacing: 0.5px; }

.stat-row { display: flex; justify-content: space-between; align-items: center; font-size: 14px; font-weight: 600; gap: 10px; }
.stat-row.pos { color: var(--pos); }
.stat-row.neg { color: var(--neg); }

.no-data { color: #9ca3af; font-style: italic; }

.compare-actions { display: flex; gap: 15px; margin-bottom: 20px; }
.btn-clear-modern { 
  display: inline-flex; 
  align-items: center; 
  gap: 6px; 
  background: var(--surface); 
  border: 1px solid var(--border); 
  color: #4b5563; 
  padding: 8px 16px; 
  border-radius: 8px; 
  font-weight: 600; 
  cursor: pointer; 
  transition: all 0.2s; 
  font-size: 14px; 
}
.btn-clear-modern:hover { 
  background: #f3f4f6; 
  color: #1f2937;
  border-color: #d1d5db; 
}

@media (max-width: 768px) {
  .compare-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
  .table-responsive {
    width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    margin-bottom: 20px;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }
  table.compare-table {
    min-width: 480px; 
  }
  .aspect-col {
    width: 110px;
    min-width: 110px;
    max-width: 110px;
    padding: 8px 10px !important;
    font-size: 13px;
  }
  .aspect-name {
    width: 110px;
    min-width: 110px;
    max-width: 110px;
    padding: 8px 10px !important;
    font-size: 13px;
    word-break: break-word;
  }
  .stat-cell {
    padding: 6px 8px !important;
  }
  .stat-box {
    padding: 8px 10px;
    min-width: 75px;
  }
  .game-title {
    font-size: 14px;
    padding: 8px 4px;
  }
  .controls {
    flex-direction: column;
    width: 100%;
  }
  .controls label, .controls button {
    width: 100%;
    justify-content: center;
  }
}
</style>