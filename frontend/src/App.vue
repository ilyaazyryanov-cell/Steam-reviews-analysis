<script setup>
import { ref } from 'vue'

const search = ref('')
const games = ref([])
const selectedGame = ref(null)
const aspects = ref([])
const sortBy = ref('aspect')
const descending = ref(false)
const excludeNeutral = ref(false)
const filterAspect = ref('')
const minPositive = ref(0)
const suggestions = ref([])

async function searchGames() {
  const response = await fetch(
    `http://127.0.0.1:8000/games?search=${encodeURIComponent(search.value)}&aspect=${encodeURIComponent(filterAspect.value)}&min_positive=${minPositive.value}`
  )

  games.value = await response.json()
}

async function getSuggestions() {
  if (search.value.length < 3) {
    suggestions.value = []
    return
  }

  const response = await fetch(
    `http://127.0.0.1:8000/games?search=${encodeURIComponent(search.value)}`
  )

  suggestions.value = await response.json()
}

async function selectSuggestion(game) {
  search.value = game.name
  suggestions.value = []

  await searchGames()
}

function resetFilters() {
  filterAspect.value = ''
  minPositive.value = 0
  searchGames()
}

async function selectGame(game) {
  selectedGame.value = game
  await loadAspects()
}

async function loadAspects() {
  if (!selectedGame.value) {
    return
  }

  const response = await fetch(
    `http://127.0.0.1:8000/games/${selectedGame.value.id}/aspects?exclude_neutral=${excludeNeutral.value}&sort_by=${sortBy.value}&descending=${descending.value}`
  )

  aspects.value = await response.json()
}


</script>

<template>
  <main class="container">
    <h1>Steam Analysis</h1>

    <div class="search-wrapper">
      <div class="search-block">
        <input
          v-model="search"
          type="text"
          placeholder="Search for a game..."
          @input="getSuggestions"
          @keyup.enter="searchGames"
        />

        <button @click="searchGames">
          Search
        </button>
      </div>

      <div v-if="suggestions.length > 0" class="suggestions">
        <button
          v-for="game in suggestions"
          :key="game.id"
          class="suggestion"
          @click="selectSuggestion(game)"
        >
          {{ game.name }}
        </button>
      </div>
    </div>

    <div class="game-filters">
      <label>
        <span>Aspect:</span>

        <select v-model="filterAspect">
          <option value="">All aspects</option>
          <option value="Gameplay">Gameplay</option>
          <option value="Graphics & Art Style">Graphics & Art Style</option>
          <option value="Difficulty">Difficulty</option>
          <option value="Story, Characters & Lore">Story, Characters & Lore</option>
          <option value="Content & Replayability">Content & Replayability</option>
          <option value="Audio">Audio</option>
          <option value="Value & Monetization">Value & Monetization</option>
        </select>
      </label>

      <label>
        <span>Minimum positive:</span>

        <div class="percentage-input">
          <input
            v-model.number="minPositive"
            type="number"
            min="0"
            max="100"
            step="1"
          />

          <span>%</span>
        </div>
      </label>

      <button @click="searchGames">
        Apply filter
      </button>

      <button @click="resetFilters">
        Reset filters
      </button>
    </div>

    <div v-if="games.length > 0" class="games-list">
      <h2>Games</h2>

      <button
        v-for="game in games"
        :key="game.id"
        class="game-button"
        @click="selectGame(game)"
      >
        {{ game.name }}
      </button>
    </div>

    <div v-if="selectedGame" class="game-section">
      <h2>{{ selectedGame.name }}</h2>

      <div class="filters">
        <label>
          <input
            v-model="excludeNeutral"
            type="checkbox"
            @change="loadAspects"
          />

          Exclude neutral mentions
        </label>

        <label>
          Sort by:

          <select v-model="sortBy" @change="loadAspects">
            <option value="aspect">Aspect</option>
            <option value="mentions">Mentions</option>
            <option value="positive">Positive %</option>
            <option value="negative">Negative %</option>
            <option value="neutral">Neutral %</option>
          </select>
        </label>

        <label>
          <input
            v-model="descending"
            type="checkbox"
            @change="loadAspects"
          />

          Descending
        </label>
      </div>

      <table>
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
          <tr
            v-for="aspect in aspects"
            :key="aspect.aspect"
          >
            <td>{{ aspect.aspect }}</td>
            <td>{{ aspect.mentions }}</td>
            <td>{{ aspect.positive_percent }}%</td>
            <td>{{ aspect.negative_percent }}%</td>
            <td>{{ aspect.neutral_percent }}%</td>
          </tr>
        </tbody>
      </table>
    </div>
  </main>
</template>

<style>
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: Arial, sans-serif;
  background: #f4f5f7;
  color: #222;
}

button,
input,
select {
  font-family: inherit;
}

.container {
  max-width: 1100px;
  margin: 0 auto;
  padding: 40px 24px;
}

h1 {
  margin: 0 0 8px;
  font-size: 32px;
}

.search-wrapper {
  position: relative;
  margin-top: 28px;
  margin-bottom: 24px;
}

.search-block {
  display: flex;
  gap: 10px;
  margin-bottom: 0;
}

.search-block input {
  flex: 1;
  min-width: 0;
  padding: 12px 14px;
  font-size: 16px;
  border: 1px solid #ccc;
  border-radius: 6px;
  background: white;
}

.search-block input:focus {
  outline: none;
  border-color: #666;
}

.search-block button,
.game-filters button {
  padding: 10px 18px;
  border: 1px solid #bbb;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 14px;
}

.search-block button:hover,
.game-filters button:hover {
  background: #eee;
}

.suggestions {
  position: absolute;
  top: 100%;
  left: 0;
  right: 110px;
  z-index: 10;
  overflow: hidden;
  background: white;
  border: 1px solid #ccc;
  border-top: none;
  border-radius: 0 0 6px 6px;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08);
}

.suggestion {
  display: block;
  width: 100%;
  padding: 11px 14px;
  border: none;
  border-bottom: 1px solid #eee;
  background: white;
  text-align: left;
  cursor: pointer;
  font-size: 14px;
}

.suggestion:last-child {
  border-bottom: none;
}

.suggestion:hover {
  background: #f5f5f5;
}

.game-filters {
  display: flex;
  align-items: end;
  gap: 16px;
  flex-wrap: wrap;
  padding: 18px;
  margin-bottom: 24px;
  background: white;
  border: 1px solid #ddd;
  border-radius: 8px;
}

.game-filters label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
}

.percentage-input {
  display: flex;
  align-items: center;
  gap: 6px;
}

.game-filters select,
.game-filters input {
  padding: 9px 10px;
  font-size: 14px;
  border: 1px solid #ccc;
  border-radius: 5px;
  background: white;
}

.game-filters input {
  width: 90px;
}

.games-list {
  margin-bottom: 24px;
  padding: 20px;
  background: white;
  border: 1px solid #ddd;
  border-radius: 8px;
}

.games-list h2 {
  margin-top: 0;
}

.game-button {
  display: block;
  width: 100%;
  padding: 12px 14px;
  margin-bottom: 8px;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: white;
  text-align: left;
  cursor: pointer;
  font-size: 15px;
}

.game-button:last-child {
  margin-bottom: 0;
}

.game-button:hover {
  background: #f5f5f5;
}

.game-section {
  padding: 20px;
  background: white;
  border: 1px solid #ddd;
  border-radius: 8px;
}

.game-section h2 {
  margin-top: 0;
}

.filters {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.filters label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 14px;
}

.filters select {
  padding: 7px 10px;
  font-size: 14px;
  border: 1px solid #ccc;
  border-radius: 5px;
  background: white;
}

.filters input {
  margin: 0;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  padding: 12px;
  border-bottom: 1px solid #ddd;
  text-align: left;
}

th {
  background: #f0f1f3;
  font-weight: 600;
}

tbody tr:hover {
  background: #fafafa;
}
</style>