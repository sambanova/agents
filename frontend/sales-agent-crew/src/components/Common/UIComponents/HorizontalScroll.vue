<template>
    <div class="horizontal-scroll-wrapper">
      <!-- Left Arrow: only shows if content is scrolled to the right -->
      <button v-if="showLeftArrow" class="scroll-arrow left" @click="scrollLeft">
        ‹
      </button>
  
      <!-- Scrollable container that displays slot content -->
      <div class="scroll-container" ref="scrollContainer">
        <slot></slot>
      </div>
  
      <!-- Right Arrow: only shows if more content is available to the right -->
      <button v-if="showRightArrow" class="scroll-arrow right" @click="scrollRight">
        ›
      </button>
    </div>
  </template>
  
  <script setup>
  import { ref, onMounted, onUnmounted, nextTick } from 'vue';
  
  const scrollContainer = ref(null);
  const showLeftArrow = ref(false);
  const showRightArrow = ref(false);
  let observer = null;
  
  function updateArrows() {
    if (scrollContainer.value) {
      const el = scrollContainer.value;
      // Show left arrow if scrolled from the beginning
      showLeftArrow.value = el.scrollLeft > 0;
      // Show right arrow if the content is wider than the visible area
      showRightArrow.value = el.scrollLeft < (el.scrollWidth - el.clientWidth);
    }
  }
  
  function scrollLeft() {
    if (scrollContainer.value) {
      scrollContainer.value.scrollLeft -= 200;
      setTimeout(updateArrows, 150);
    }
  }
  
  function scrollRight() {
    if (scrollContainer.value) {
      scrollContainer.value.scrollLeft += 200;
      setTimeout(updateArrows, 150);
    }
  }
  
  onMounted(() => {
    // Wait for initial DOM render
    nextTick(updateArrows);
  
    if (scrollContainer.value) {
      scrollContainer.value.addEventListener('scroll', updateArrows);
    }
    window.addEventListener('resize', updateArrows);
  
    // Set up a MutationObserver to detect changes in the slot content.
    observer = new MutationObserver(() => {
      // Delay slightly to allow DOM updates to complete.
      setTimeout(updateArrows, 100);
    });
    if (scrollContainer.value) {
      observer.observe(scrollContainer.value, { childList: true, subtree: true });
    }
  });
  
  onUnmounted(() => {
    if (scrollContainer.value) {
      scrollContainer.value.removeEventListener('scroll', updateArrows);
    }
    window.removeEventListener('resize', updateArrows);
    if (observer) {
      observer.disconnect();
    }
  });
  </script>
  
  <style scoped>
  .horizontal-scroll-wrapper {
    position: relative;
    width: 100%;
    
    overflow: hidden;
    /* background: #f9f9f9; */
    border-radius: 12px;
    /* box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); */
  }
  
  .scroll-container {
    overflow-x: auto;
    white-space: nowrap;
    scroll-behavior: smooth;
    padding: 8px 2px; /* Minimal horizontal padding to eliminate differences */
    -ms-overflow-style: none;
    scrollbar-width: none;
  }
  .scroll-container::-webkit-scrollbar {
    display: none;
  }
  
  /* Arrow button styling */
  .scroll-arrow {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    background: rgba(0, 0, 0, 0.6);
    border: none;
    color: #fff;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    cursor: pointer;
    z-index: 2;
    transition: opacity 0.3s ease;
  }
  .scroll-arrow.left {
    left: 10px;
  }
  .scroll-arrow.right {
    right: 10px;
  }
  </style>
  