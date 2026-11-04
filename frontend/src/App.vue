<script setup>
import { ref } from 'vue'
import GameList from './components/GameList.vue'
import GameDetails from './components/GameDetails.vue'
import GameCompare from './components/GameCompare.vue'

const currentView = ref('list')
const selectedGame = ref(null)
const compareIds = ref(new Set())
const showHelpModal = ref(false)

function goHome() {
  currentView.value = 'list'
}

function goToDetails(game) {
  selectedGame.value = game
  currentView.value = 'details'
}

function goToCompare() {
  if (compareIds.value.size > 0) currentView.value = 'compare'
}

function toggleCompare(gameId) {
  const newSet = new Set(compareIds.value)
  if (newSet.has(gameId)) {
    newSet.delete(gameId)
  } else {
    newSet.add(gameId)
  }
  compareIds.value = newSet
}

function clearCompare() {
  compareIds.value = new Set()
  currentView.value = 'list'
}
</script>

<template>
  <main class="app-container">
    <header class="header">
      <div class="logo-container">
        <svg class="logo-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <circle cx="7" cy="17" r="4"></circle>
          <circle cx="17" cy="8" r="3"></circle>
          <path d="M9.5 14.5L14.5 10.5"></path>
          <path d="M17 11v6l-4-3"></path>
          <path d="M3 3l18 18" stroke-opacity="0.2"></path>
        </svg>
        <h1>Steam Analysis</h1>
      </div>
      
      <nav class="nav-buttons">
        <button @click="showHelpModal = true" class="btn-help">Help</button>
        <button @click="goHome" :class="{ active: currentView === 'list' }">Home</button>
        <button @click="goToCompare" :disabled="compareIds.size === 0" :class="{ active: currentView === 'compare' }">
          Compare ({{ compareIds.size }})
        </button>
      </nav>
    </header>

    <GameList 
      v-if="currentView === 'list'" 
      :compareIds="compareIds" 
      @toggle-compare="toggleCompare" 
      @select-game="goToDetails" 
    />
    
    <GameDetails 
      v-else-if="currentView === 'details'" 
      :key="selectedGame.id"
      :game="selectedGame" 
      :compareIds="compareIds"
      @toggle-compare="toggleCompare" 
      @go-back="goHome" 
      @select-game="goToDetails" 
    />
    
    <GameCompare 
      v-else-if="currentView === 'compare'" 
      :compareIds="compareIds" 
      @go-back="goHome" 
      @clear-compare="clearCompare"
    />

    <div v-if="showHelpModal" class="modal-overlay" @click.self="showHelpModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>How to use Steam Analysis</h3>
          <button @click="showHelpModal = false" class="close-btn" aria-label="Close">✕</button>
        </div>
        <div class="modal-body">
          <ul class="help-list">
            <li><strong>Search:</strong> Находите игры по названию или фильтруйте главную страницу по аспектам (например, "Performance"). Есть возможность установить минимальный положительный и максимальный негативный % отзывов по аспекту.</li>
            <li><strong>Game Details:</strong> Кликните на карточку игры, чтобы увидеть детальную статистику по каждому аспекту. Доступен фильтр отзывов только за последние 90 дней и сортировка по упоминаниям, % позитивных/негативных/нейтральных, названию аспекта. Галочка "Descending" сортирует по убыванию. Можно исключить нейтральные отзывы из подсчёта галочкой "Exclude Neutral". Внизу страницы можно посмотреть похожие игры по оценкам.</li>
            <li><strong>Compare Games:</strong> Ставьте галочку "Add to compare" на карточках игр. Выбрав несколько, нажмите "Compare" в верхнем меню, чтобы наглядно сравнить их сильные и слабые стороны. Победители выделяются зелёной заливкой. Вы можете очистить список сравнения из режима "Compare", нажав кнопку "Clear All".</li>
          </ul>
        </div>
      </div>
    </div>
  </main>
</template>

<style>
:root { 
  --primary: #2563eb; 
  --bg: #f3f4f6; 
  --surface: #ffffff; 
  --text: #1f2937; 
  --border: #e5e7eb; 
  --pos: #10b981; 
  --neg: #ef4444; 
}
body { margin: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: var(--bg); color: var(--text); }
.app-container { max-width: 1200px; margin: 0 auto; padding: 20px; }

.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }

.logo-container { display: flex; align-items: center; gap: 12px; }
.logo-container h1 { margin: 0; font-size: 24px; color: var(--text); }
.logo-icon { width: 36px; height: 36px; color: var(--primary); }

.nav-buttons { display: flex; gap: 10px; }
.nav-buttons button { padding: 10px 20px; border: none; background: #e5e7eb; cursor: pointer; border-radius: 8px; font-weight: bold; transition: 0.2s; }
.nav-buttons button.active { background: var(--primary); color: white; }
.nav-buttons button:disabled { opacity: 0.5; cursor: not-allowed; }

.table-responsive { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); background: var(--surface); }
.aspects-table { width: 100%; border-collapse: collapse; min-width: 600px; }
.aspects-table th, .aspects-table td { padding: 12px 15px; text-align: left; border-bottom: 1px solid var(--border); }
.aspects-table th { background: #f9fafb; font-weight: 600; color: #4b5563; }

.btn-back-modern {
  display: inline-flex; align-items: center; gap: 8px; background: var(--surface); border: 1px solid var(--border);
  color: var(--text); padding: 8px 16px; border-radius: 8px; font-weight: 600; cursor: pointer;
  transition: all 0.2s; margin-bottom: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); font-size: 14px;
}
.btn-back-modern:hover { background: #f9fafb; transform: translateX(-4px); border-color: #d1d5db; }

.btn-help { background: transparent !important; color: #4b5563 !important; border: 1px solid #d1d5db !important; }
.btn-help:hover { background: #f3f4f6 !important; }

.modal-overlay { 
  position: fixed; 
  top: 0; 
  left: 0; 
  right: 0; 
  bottom: 0; 
  background: rgba(0,0,0,0.5); 
  display: flex; 
  justify-content: center; 
  align-items: center; 
  z-index: 100; 
  padding: 16px; 
  box-sizing: border-box; 
}
.modal-content { 
  background: var(--surface); 
  width: 100%; 
  max-width: 600px; 
  max-height: 85vh; 
  border-radius: 12px; 
  display: flex; 
  flex-direction: column; 
  box-shadow: 0 10px 25px rgba(0,0,0,0.2); 
  animation: fadeIn 0.2s ease-out; 
  overflow: hidden; 
  box-sizing: border-box; 
}
.modal-header { 
  padding: 18px 20px; 
  border-bottom: 1px solid var(--border); 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
}
.modal-header h3 { margin: 0; font-size: 18px; color: var(--text); }
.close-btn { background: none; border: none; font-size: 20px; cursor: pointer; color: #9ca3af; transition: 0.2s; padding: 4px; line-height: 1; }
.close-btn:hover { color: #ef4444; }
.modal-body { padding: 20px; font-size: 14px; line-height: 1.6; color: #374151; overflow-y: auto; }
.help-list { margin: 0; padding-left: 20px; }
.help-list li { margin-bottom: 15px; }

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 768px) {
  .app-container { padding: 10px; }
  .header { flex-direction: column; gap: 15px; align-items: stretch; text-align: center; }
  .nav-buttons { justify-content: center; width: 100%; flex-wrap: wrap; }
  .nav-buttons button { flex: 1 1 30%; }
  .logo-container { justify-content: center; }
}
</style>