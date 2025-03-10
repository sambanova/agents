<template>
    <div class="markdown-content">
      <transition-group name="fade" tag="div">
        <span
          v-for="(item, index) in displayedWords"
          :key="index"
          :style="{ opacity: item.isNew ? 0.6 : 1 }"
        >
          {{ item.word }}&nbsp;
        </span>
      </transition-group>
    </div>
  </template>
  
  <script>
  export default {
    name: 'AnimatedMarkdown',
    props: {
      text: {
        type: String,
        default: '',
      },
      // Delay between words in milliseconds (typing effect)
      typingDelay: {
        type: Number,
        default: 100,
      },
      // Time after which a new word fades to full opacity
      fadeDelay: {
        type: Number,
        default: 1000,
      },
    },
    data() {
      return {
        displayedWords: [], // Each item is { word: string, isNew: boolean }
        allWords: [],
        typingInterval: null,
        currentIndex: 0,
      };
    },
    watch: {
      text(newVal) {
        this.startTyping(newVal);
      },
    },
    mounted() {
      this.startTyping(this.text);
    },
    methods: {
      startTyping(newText) {
        // Clear any previous typing
        if (this.typingInterval) clearInterval(this.typingInterval);
        this.displayedWords = [];
        this.allWords = newText.split(" ");
        this.currentIndex = 0;
        this.typingInterval = setInterval(() => {
          if (this.currentIndex < this.allWords.length) {
            // Push the next word with isNew true
            this.displayedWords.push({ word: this.allWords[this.currentIndex], isNew: true });
            const idx = this.currentIndex;
            // After fadeDelay, mark this word as "old" (full opacity)
            setTimeout(() => {
              this.$set(this.displayedWords, idx, { word: this.allWords[idx], isNew: false });
            }, this.fadeDelay);
            this.currentIndex++;
          } else {
            clearInterval(this.typingInterval);
          }
        }, this.typingDelay);
      },
    },
  };
  </script>
  
  <style scoped>
  .markdown-content {
    font-family: 'Inter', sans-serif;
    font-size: 16px;
    line-height: 24px;
  }
  
  /* Transition for words fading in/out */
  .fade-enter-active, .fade-leave-active {
    transition: opacity 0.5s;
  }
  .fade-enter-from, .fade-leave-to {
    opacity: 0;
  }
  </style>
  