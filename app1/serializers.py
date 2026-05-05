from rest_framework import serializers
from .models import *


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        exclude = ['quiz']


class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True)

    class Meta:
        model = Quiz
        fields = ['course', 'title', 'questions']

    def create(self, validated_data):
        questions_data = validated_data.pop('questions')
        quiz = Quiz.objects.create(**validated_data)

        for q in questions_data:
            Question.objects.create(quiz=quiz, **q)

        return quiz