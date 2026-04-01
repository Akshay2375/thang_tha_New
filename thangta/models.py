from django.contrib.auth.models import AbstractUser
from django.db import models

# ==========================================
# 1. USER AUTHENTICATION MODEL
# ==========================================
class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        JUDGE = 'JUDGE', 'Judge'
        SCORER = 'SCORER', 'Scorer'

    role = models.CharField(
        max_length=50, 
        choices=Role.choices, 
        default=Role.SCORER
    )
    
    # Location fields for officials
    district = models.CharField(max_length=100, null=True, blank=True)
    district_code = models.CharField(max_length=20, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.role == self.Role.ADMIN:
            self.is_staff = True
            self.is_superuser = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} - {self.get_role_display()}"


# ==========================================
# 2. TOURNAMENT MODEL
# ==========================================
class Tournament(models.Model):
    name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    battle_rings = models.IntegerField(default=0)

    def __str__(self):
        return self.name


# ==========================================
# 3. PARTICIPANT MODEL
# ==========================================
class Participant(models.Model):
    # --- Choices ---
    class GenderChoices(models.TextChoices):
        MALE = 'Male', 'Male'
        FEMALE = 'Female', 'Female'

    class EventTypeChoices(models.TextChoices):
        PHUNABA_AMA = 'Phunaba-Ama', 'Phunaba-Ama'
        PHUNABA_ANISHUBA = 'Phunaba-Anishuba', 'Phunaba-Anishuba'

    class AgeCategory(models.TextChoices):
        UNDER_14 = 'U14', 'Under 14'
        UNDER_18 = 'U18', 'Under 18'
        OVER_18 = 'O18', 'Over 18'

    class WeightCategory(models.TextChoices):
        MINUS_21 = '-21', '-21 Kg'
        MINUS_25 = '-25', '-25 Kg'
        MINUS_29 = '-29', '-29 Kg'
        MINUS_33 = '-33', '-33 Kg'
        MINUS_37 = '-37', '-37 Kg'
        MINUS_40 = '-40', '-40 Kg'
        MINUS_41 = '-41', '-41 Kg'
        MINUS_44 = '-44', '-44 Kg'
        MINUS_45 = '-45', '-45 Kg'
        MINUS_49 = '-49', '-49 Kg'
        MINUS_52 = '-52', '-52 Kg'
        MINUS_53 = '-53', '-53 Kg'
        MINUS_56 = '-56', '-56 Kg'
        MINUS_75 = '-75', '-75 Kg'
        PLUS_53 = '+53', '+53 Kg'

    # --- Relationships ---
    tournament = models.ForeignKey(
        Tournament, 
        on_delete=models.CASCADE, 
        related_name='participants',
        null=True, blank=True
    )

    # --- Personal Information ---
    name = models.CharField(max_length=200, null=True, blank=True)
    actual_age = models.IntegerField(null=True, blank=True, help_text="Age in numbers")
    
    date_of_birth = models.DateField(null=True, blank=True) # Add this!
    age = models.IntegerField(default = 0)
    
    gender = models.CharField(max_length=10, choices=GenderChoices.choices, null=True, blank=True)
    contact = models.CharField(max_length=15, null=True, blank=True)
    
    # --- Location Data ---
    district = models.CharField(max_length=100)
    district_code = models.CharField(max_length=20)

    # --- Tournament Categories ---
    event_type = models.CharField(max_length=50, choices=EventTypeChoices.choices, null=True, blank=True)
    
    age_category = models.CharField(
        max_length=3, 
        choices=AgeCategory.choices,
        help_text="Select the participant's age group."
    )
    
    weight_category = models.CharField(
        max_length=4, 
        choices=WeightCategory.choices,
        help_text="Select the participant's weight class."
    )

    def __str__(self):
        display_name = self.name if self.name else "Unnamed Participant"
        return f"{display_name} | {self.district} - {self.get_age_category_display()}"


# ==========================================
# 4. MATCH MODEL
# ==========================================
class Match(models.Model):
    # 1. Grouping Criteria
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=50)
    age_category = models.CharField(max_length=3)
    weight_category = models.CharField(max_length=4)
    gender = models.CharField(max_length=10)
    
    # 2. Match State Control
    is_active = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    
    # 3. Progression Tracking
    round_number = models.IntegerField(default=1)
    current_round = models.IntegerField(default=1) # Tracks Round 1, Round 2, or 3 (Tie Breaker)
    # Add this inside your Match class
    current_sub_round = models.IntegerField(default=1)
    match_sequence = models.IntegerField(help_text="Order of the match in this round")
    current_sub_round = models.IntegerField(default=1)
    
    # 4. Match Structure
    ring_number = models.IntegerField(default=1)
    
    # Corners
    participant_red = models.ForeignKey(Participant, related_name='matches_as_red', on_delete=models.CASCADE)
    participant_blue = models.ForeignKey(Participant, related_name='matches_as_blue', on_delete=models.CASCADE, null=True, blank=True)
    
    # Winner Selection
    winner = models.ForeignKey(Participant, related_name='matches_won', on_delete=models.SET_NULL, null=True, blank=True)
    
    @property
    def age_display(self):
        """Safely translates the short code to the full age name."""
        age_map = {'U14': 'Under 14', 'U18': 'Under 18', 'O18': 'Over 18'}
        return age_map.get(self.age_category, self.age_category)

    @property
    def weight_display(self):
        """Safely ensures Kg is added to the weight."""
        if self.weight_category and "Kg" not in str(self.weight_category):
            return f"{self.weight_category} Kg"
        return self.weight_category

    @property
    def full_category_name(self):
        """Combines them all for the Match Cards."""
        return f"{self.event_type} | {self.gender} | {self.age_display} | {self.weight_display}"    
    def __str__(self):
        blue_name = self.participant_blue.name if self.participant_blue else "BYE"
        return f"Round {self.round_number} | Ring {self.ring_number} | {self.participant_red.name} (RED) vs {blue_name} (BLUE)"


# ==========================================
# 5. SCORE MODEL
# ==========================================
class Score(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='scores')
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    scorer = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='submitted_scores')
    
    points = models.IntegerField(default=1)
    
    # Fields for Judge Control
    round_num = models.IntegerField(default=1) # Tracks if this score was in Round 1, 2, or 3
    # sub_round = models.IntegerField(default=1) 
    is_foul = models.BooleanField(default=False)
    foul_reason = models.CharField(max_length=255, blank=True, null=True)
    is_flagged = models.BooleanField(default=False) 
    
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        foul_str = f" (FOUL: {self.foul_reason})" if self.is_foul else ""
        scorer_name = self.scorer.username if self.scorer else "Unknown Scorer"
        return f" {self.points} pts for {self.participant.name} by {scorer_name}{foul_str}"
    
class District(models.Model):
    name = models.CharField(max_length=100, unique=True)
    access_code = models.CharField(max_length=50) # The secret password for coaches

    def __str__(self):
        return self.name